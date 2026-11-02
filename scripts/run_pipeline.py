"""Batch pipeline: fetch new reports -> insert unseen RAW rows -> dbt build."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from api import EventsAPI, atomic_json, utc_now
from ingest import ENDPOINTS, prepare_load_files
from snowflake_io import connect, read_config, last_success, load_batch, complete_run

ROOT = Path(__file__).resolve().parents[1]


def pipeline(args):
    """Resume one run or create a new batch using the last successful cutoff."""
    with connect(read_config()) as connection:
        if args.run_dir:
            run_dir = Path(args.run_dir).resolve()
        else:
            run_dir = ROOT / 'data/landing' / f'extraction_date={datetime.now(timezone.utc):%Y-%m-%d}' / uuid.uuid4().hex
        run_dir.mkdir(parents=True, exist_ok=True)
        state = run_dir / 'run.json'
        if state.exists():
            run = json.loads(state.read_text())
            if args.full or args.since:
                raise ValueError('Resume with --run-dir only; the original request is saved')
        else:
            previous = last_success(connection)
            since = None if args.full else (args.since or (previous['receipt_cutoff'] if previous else None))
            run = {'batch_id': uuid.uuid4().hex + uuid.uuid4().hex, 'receipt_cutoff': utc_now(),
                   'received_since': since, 'status': 'EXTRACTING'}
            if since and datetime.fromisoformat(since) > datetime.fromisoformat(run['receipt_cutoff']):
                raise ValueError('--since cannot be in the future')
            atomic_json(state, run)
        print(f'Run directory: {run_dir}', flush=True)
        api = EventsAPI()
        checkpoints = {}
        for endpoint in ENDPOINTS:
            # Completed pages are reused when resuming; no parent snapshot is read.
            checkpoints[endpoint] = api.extract(
                endpoint, run_dir / endpoint,
                received_since=run['received_since'] if endpoint != 'users' else None)
            print(f"{endpoint}: {sum(p['rows'] for p in checkpoints[endpoint]['pages']):,} fetched", flush=True)
        files = prepare_load_files(run_dir, run['batch_id'], checkpoints)
        result = load_batch(connection, run, files)
        atomic_json(run_dir / 'load_result.json', result)
        run['status'] = 'RAW_LOADED'
        atomic_json(state, run)
        # Explicit variables select this cutoff. SNAPSHOT_ID is retained in the mart
        # only for schema compatibility; its value now labels this analytical run.
        variables = {'run_id': run['batch_id'], 'receipt_cutoff': run['receipt_cutoff']}
        target = run_dir / 'dbt_target'
        command = [str(ROOT / '.venv-dbt/bin/python'), str(ROOT / 'scripts/run_dbt.py'),
                   'build', '--vars', json.dumps(variables), '--target-path', str(target)]
        result = subprocess.run(command, cwd=ROOT)
        artifact = target / 'run_results.json'
        if result.returncode or not artifact.exists():
            run['status'] = 'DBT_FAILED'
            atomic_json(state, run)
            raise RuntimeError('dbt failed; successful cutoff unchanged. Resume this run directory.')
        results = json.loads(artifact.read_text())['results']
        if any(row['status'] in {'error', 'fail', 'skipped'} for row in results):
            raise RuntimeError('Blocking dbt results; successful cutoff unchanged')
        complete_run(connection, run['batch_id'])
        run.update(status='COMPLETE', completed_at=utc_now())
        atomic_json(state, run)
        print(json.dumps(run), flush=True)


def main():
    """Prevent concurrent local runs and start a normal, full, or resumed batch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', help='Reuse this directory to resume an interrupted run')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--full', action='store_true', help='Fetch all reports; merge inserts only unseen ones')
    mode.add_argument('--since', help='Deliberate receipt lookback, ISO timestamp with timezone')
    args = parser.parse_args()
    if args.since and datetime.fromisoformat(args.since).tzinfo is None:
        raise ValueError('--since requires a timezone offset')
    os.chdir(ROOT)
    (ROOT / 'data').mkdir(exist_ok=True)
    with (ROOT / 'data/pipeline.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another local pipeline is running') from None
        pipeline(args)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Keep connector details and credentials out of console errors.
        message = str(error) if isinstance(error, (ValueError, RuntimeError)) else 'Operation failed; sensitive details hidden'
        print(f'{type(error).__name__}: {message}', file=sys.stderr)
        raise SystemExit(1)
