"""Fresh API snapshot -> append-only RAW -> dbt build; baseline defaults stay pinned."""
import argparse
from collections import Counter
from datetime import datetime, timedelta
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from api import EventsAPI, atomic_json, sha256, utc_now
from ingest import ENDPOINTS, canonical, finalize_snapshot, verify_snapshot
from snowflake_io import connect, load_snapshot, read_config

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'e943b3aefc3411575c251ada7404c7013b54bf9510e8d37e9e69bd2f80bf863a'
STATE = ROOT / 'data/pipeline_state.json'


def merge_overlap(parent, delta):
    """Retain maximum observed multiplicity of identical full payloads, not business IDs."""
    prior = Counter(canonical(row) for row in parent)
    incoming = Counter()
    result = list(parent)
    for row in delta:
        key = canonical(row)
        incoming[key] += 1
        if incoming[key] > prior[key]:
            result.append(row)
    return result


def publish_success(run, state_path=STATE):
    """Never advance on a failed phase or move a newer successful watermark backwards."""
    if run.get('status') != 'COMPLETE':
        raise ValueError('Only fully successful runs can advance the checkpoint')
    state_path = Path(state_path)
    existing = json.loads(state_path.read_text()) if state_path.exists() else None
    if existing and datetime.fromisoformat(existing['receipt_cutoff']) > datetime.fromisoformat(run['receipt_cutoff']):
        return
    atomic_json(state_path, {'snapshot': run['snapshot'], 'snapshot_id': run['snapshot_id'],
                            'receipt_cutoff': run['receipt_cutoff'], 'completed_at': run['completed_at']})


def prepare_fresh(run_dir, run, full=False):
    parent_manifest = verify_snapshot(ROOT / run['parent_snapshot']) if not full else None
    api = EventsAPI()
    frames, sources, endpoint_meta, capture = {}, {}, {}, {}
    building = run_dir / 'building'
    source_dir = building / 'sources'
    source_dir.mkdir(parents=True, exist_ok=True)
    for endpoint in ENDPOINTS:
        since = None
        if endpoint != 'users' and not full:
            since = (datetime.fromisoformat(run['parent_cutoff']) - timedelta(hours=24)).isoformat()
        extract_dir = run_dir / 'extractions' / endpoint
        extraction = api.extract(endpoint, extract_dir, received_since=since)
        records = []
        for page in extraction['pages']:
            records.extend(json.loads((extract_dir / page['file']).read_text())['data'])
        fetched = len(records)
        if endpoint != 'users' and not full:
            meta = parent_manifest['endpoints'][endpoint]
            previous = json.loads((ROOT / run['parent_snapshot'] / meta['source_file']).read_text())['records']
            records = merge_overlap(previous, records)
        frames[endpoint] = records
        target = source_dir / f'{endpoint}.json'
        atomic_json(target, {'records': records, 'complete': True})
        sources[f'sources/{endpoint}.json'] = sha256(target)
        endpoint_meta[endpoint] = {'rows': len(records), 'source_file': f'sources/{endpoint}.json',
                                  'source_file_sha256': sha256(target), 'record_array_key': 'records',
                                  'pagination_exhausted': True,
                                  'receipt_cutoff_utc': run['receipt_cutoff'] if endpoint != 'users' else None}
        capture[endpoint] = {'started_at': extraction['started_at'], 'finished_at': extraction['finished_at'],
                             'received_since': since, 'pages': len(extraction['pages']), 'fetched_rows': fetched}
        originals = source_dir / 'extractions' / endpoint
        originals.mkdir(parents=True, exist_ok=True)
        for original in [*[extract_dir / page['file'] for page in extraction['pages']], extract_dir / 'checkpoint.json']:
            destination = originals / original.name
            shutil.copyfile(original, destination)
            sources[destination.relative_to(building).as_posix()] = sha256(destination)
        print(f'{endpoint}: fetched {fetched:,}; full snapshot contains {len(records):,} records', flush=True)
    if parent_manifest:
        target = source_dir / 'parent_manifest.json'
        shutil.copyfile(ROOT / run['parent_snapshot'] / 'manifest.json', target)
        sources[target.relative_to(building).as_posix()] = sha256(target)
    identity = {'format_version': 1, 'purpose': 'FULL_BASELINE', 'source_files': sources,
                'endpoints': endpoint_meta, 'analysis_receipt_cutoff_utc': run['receipt_cutoff'],
                'users_capture': capture['users'], 'capture': capture,
                'parent_snapshot_id': parent_manifest['snapshot_id'] if parent_manifest else None,
                'extraction_mode': 'fresh_full' if full else 'parent_plus_receipt_overlap',
                'overlap_rule': 'Maximum multiplicity of identical complete payloads; never session-id deduplication',
                'limitations': 'No source snapshot isolation; incremental lookback cannot guarantee older backdated receipts or deletions',
                'source_ordinal': 'Zero-based position in frozen endpoint array; parent order retained then new observations appended'}
    return finalize_snapshot(building, frames, identity)


def pipeline(args):
    ROOT.joinpath('data').mkdir(exist_ok=True)
    run_dir = Path(args.run_dir).resolve() if args.run_dir else ROOT / 'data/pipeline_runs' / datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run_dir.mkdir(parents=True, exist_ok=True)
    run_path = run_dir / 'run.json'
    if run_path.exists():
        run = json.loads(run_path.read_text())
        if run['full'] != args.full:
            raise ValueError('Resume with the same extraction mode')
    else:
        prior = json.loads(STATE.read_text()) if STATE.exists() else {
            'snapshot': f'data/snapshots/{BASELINE}',
            'receipt_cutoff': '2026-10-27T15:21:56.773109+00:00'}
        run = {'started_at': utc_now(), 'receipt_cutoff': utc_now(), 'full': args.full,
               'parent_snapshot': prior['snapshot'], 'parent_cutoff': prior['receipt_cutoff'], 'status': 'EXTRACTING'}
        atomic_json(run_path, run)
    print(f'Run directory: {run_dir.relative_to(ROOT) if run_dir.is_relative_to(ROOT) else run_dir}', flush=True)
    if 'snapshot' not in run:
        snapshot = prepare_fresh(run_dir, run, full=args.full)
        run.update(snapshot=snapshot.as_posix(), status='FROZEN')
        atomic_json(run_path, run)
    manifest = verify_snapshot(ROOT / run['snapshot'])
    run['snapshot_id'] = manifest['snapshot_id']
    print('Snapshot:', manifest['snapshot_id'], flush=True)
    with connect(read_config()) as connection:
        result = load_snapshot(connection, ROOT / run['snapshot'], manifest)
    atomic_json(run_dir / 'load_result.json', result)
    run['status'] = 'RAW_LOADED'
    atomic_json(run_path, run)
    variables = {'snapshot_id': manifest['snapshot_id'], 'receipt_cutoff': run['receipt_cutoff']}
    command = [str(ROOT / '.venv-dbt/bin/python'), str(ROOT / 'scripts/run_dbt.py'), 'build', '--vars', json.dumps(variables)]
    print('Building dbt with this explicitly selected snapshot/cutoff; checked-in defaults are unchanged.', flush=True)
    result = subprocess.run(command, cwd=ROOT)
    artifact = ROOT / 'dbt/target/run_results.json'
    if artifact.exists():
        shutil.copyfile(artifact, run_dir / 'dbt_run_results.json')
    if result.returncode:
        run['status'] = 'DBT_FAILED'
        atomic_json(run_path, run)
        raise RuntimeError('dbt failed. Successful watermark is unchanged; inspect run results and resume this run directory.')
    results = json.loads(artifact.read_text())
    if any(row['status'] in {'error', 'fail', 'skipped'} for row in results['results']):
        raise RuntimeError('dbt results are not completely successful; watermark not advanced')
    run.update(status='COMPLETE', completed_at=utc_now(), raw_counts=result_counts(manifest),
               dbt_warnings=sum(row['status']=='warn' for row in results['results']))
    atomic_json(run_path, run)
    publish_success(run)
    print(json.dumps({key:run[key] for key in ['status','snapshot_id','receipt_cutoff','raw_counts','dbt_warnings']}), flush=True)


def result_counts(manifest):
    return {key:value['rows'] for key,value in manifest['endpoints'].items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', help='Explicit local run directory; reuse it to resume extraction/load/build')
    parser.add_argument('--full', action='store_true', help='Fetch every drive/warning page; default uses successful parent plus 24-hour overlap')
    args = parser.parse_args()
    os.chdir(ROOT)
    (ROOT/'data').mkdir(exist_ok=True)
    with (ROOT / 'data/pipeline.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another local pipeline run is active') from None
        pipeline(args)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if isinstance(error,(ValueError,RuntimeError)):
            print(f'{type(error).__name__}: {error}',file=sys.stderr)
        else:
            print(json.dumps({'error_type':type(error).__name__,'errno':getattr(error,'errno',None),
                              'message':'Pipeline failed; sensitive details hidden. Resume with the printed run directory.'}),file=sys.stderr)
        raise SystemExit(1)
