"""Snapshot-first RAW loading. Source reports are never business-deduplicated."""

import argparse
import gzip
import hashlib
import json
import shutil
import sys
from pathlib import Path

from api import EventsAPI, atomic_json, sha256, utc_now
from snowflake_io import connect, load_snapshot, read_config, setup_raw, setup_runtime_role, reconcile_notebook

ENDPOINTS = {'drives': 'session_id', 'warnings': 'warning_id', 'users': 'user_id'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def fingerprint(identity):
    return hashlib.sha256(canonical(identity).encode()).hexdigest()


def freeze(baseline, work, sample=False):
    """Import validated drive/warning bytes and checkpoint a new full users extract."""
    baseline, work = Path(baseline), Path(work)
    baseline_manifest = json.loads((baseline / 'manifest.json').read_text())
    scope = json.loads((baseline / 'scope.json').read_text())
    frames = {}
    for endpoint in ('drives', 'warnings'):
        source = baseline / f'{endpoint}.json'
        expected = baseline_manifest['sources'][endpoint]['sha256']
        if sha256(source) != expected:
            raise ValueError('Baseline checksum mismatch')
        state = json.loads(source.read_text())
        if not state['complete']:
            raise ValueError('Baseline extraction is incomplete')
        frames[endpoint] = state['records']
    users_dir = work / 'users_extraction'
    extraction = EventsAPI().extract('users', users_dir)
    frames['users'] = []
    for page in extraction['pages']:
        frames['users'].extend(json.loads((users_dir / page['file']).read_text())['data'])
    purpose = 'SMALL_TEST' if sample else 'FULL_BASELINE'
    if sample:
        # Ensure the test includes at least one real repeated session, not just distinct IDs.
        seen = {}
        pair = None
        for index, record in enumerate(frames['drives']):
            key = record.get('session_id')
            if key in seen:
                pair = [seen[key], index]
                break
            seen[key] = index
        indices = sorted(set([0, 1, 2] + (pair or [3, 4])))
        frames['drives'] = [frames['drives'][i] for i in indices]
        for endpoint in ('warnings', 'users'):
            frames[endpoint] = frames[endpoint][:5]
    building = work / ('building_test' if sample else 'building_full')
    building.mkdir(parents=True, exist_ok=True)
    source_dir = building / 'sources'
    source_dir.mkdir(exist_ok=True)
    files = {}
    metadata = {}
    for endpoint, records in frames.items():
        target = source_dir / f'{endpoint}.json'
        if endpoint in ('drives', 'warnings') and not sample:
            shutil.copyfile(baseline / f'{endpoint}.json', target)
        else:
            atomic_json(target, {'records': records, 'complete': True})
        files[f'sources/{endpoint}.json'] = sha256(target)
        metadata[endpoint] = {'rows': len(records), 'source_file': f'sources/{endpoint}.json',
                              'source_file_sha256': files[f'sources/{endpoint}.json'],
                              'record_array_key': 'records', 'pagination_exhausted': True,
                              'receipt_cutoff_utc': scope['as_of'] if endpoint != 'users' else None}
    # Retain the original complete users HTTP JSON bodies even for the test subset.
    for page in extraction['pages']:
        target = source_dir / 'users_pages' / page['file']
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(users_dir / page['file'], target)
        files['sources/users_pages/' + page['file']] = sha256(target)
    for name in ('scope.json', 'manifest.json'):
        target = source_dir / ('baseline_' + name)
        shutil.copyfile(baseline / name, target)
        files['sources/baseline_' + name] = sha256(target)
    identity = {'format_version': 1, 'purpose': purpose, 'source_files': files,
                'endpoints': metadata, 'analysis_receipt_cutoff_utc': scope['as_of'],
                'users_capture': {'started_at': extraction['started_at'], 'finished_at': extraction['finished_at']},
                'baseline_provenance': 'Validated reconstructed baseline; historical HTTP page envelopes unavailable',
                'source_ordinal': 'Zero-based position in each frozen endpoint record array'}
    return finalize_snapshot(building, frames, identity)


def finalize_snapshot(building, frames, identity):
    """Write deterministic load envelopes and publish a checked immutable snapshot."""
    building = Path(building)
    snapshot_id = fingerprint(identity)
    manifest = {'snapshot_id': snapshot_id, 'identity': identity, 'endpoints': {}}
    for endpoint, records in frames.items():
        name = f'{endpoint}.json.gz'
        path = building / name
        with path.open('wb') as raw:
            with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as zipped:
                for ordinal, record in enumerate(records):
                    envelope = {'snapshot_id': snapshot_id, 'source_ordinal': ordinal,
                                'source_id': record.get(ENDPOINTS[endpoint]),
                                'source_received_at': record.get('received_at'), 'payload': record,
                                'record_hash': hashlib.sha256(canonical(record).encode()).hexdigest(),
                                'source_file': identity['endpoints'][endpoint]['source_file'],
                                'source_file_sha256': identity['endpoints'][endpoint]['source_file_sha256']}
                    zipped.write((canonical(envelope) + '\n').encode())
        manifest['endpoints'][endpoint] = {**identity['endpoints'][endpoint], 'load_file': name, 'load_sha256': sha256(path)}
    atomic_json(building / 'manifest.json', manifest)
    destination = Path('data/snapshots') / snapshot_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if json.loads((destination / 'manifest.json').read_text()) != manifest:
            raise ValueError('Existing snapshot ID differs; immutable snapshot cannot be overwritten')
        shutil.rmtree(building)
    else:
        building.rename(destination)
    verify_snapshot(destination)
    return destination


def verify_snapshot(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    if fingerprint(manifest['identity']) != manifest['snapshot_id']:
        raise ValueError('Snapshot ID does not match its immutable identity')
    def checked_path(name):
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError('Snapshot file escapes snapshot directory')
        return path
    for name, digest in manifest['identity']['source_files'].items():
        if sha256(checked_path(name)) != digest:
            raise ValueError('Frozen source file checksum mismatch')
    for endpoint, meta in manifest['endpoints'].items():
        if endpoint not in ENDPOINTS or any(
            meta.get(key) != value for key, value in manifest['identity']['endpoints'][endpoint].items()
        ):
            raise ValueError('Snapshot endpoint metadata mismatch')
        path = checked_path(meta['load_file'])
        if sha256(path) != meta['load_sha256']:
            raise ValueError('Prepared load file checksum mismatch')
        records = json.loads(checked_path(meta['source_file']).read_text())['records']
        count = 0
        with gzip.open(path, 'rt') as source:
            for ordinal, line in enumerate(source):
                envelope = json.loads(line)
                if envelope['source_ordinal'] != ordinal or envelope['snapshot_id'] != manifest['snapshot_id']:
                    raise ValueError('Prepared ordinal/snapshot mismatch')
                if envelope['payload'] != records[ordinal]:
                    raise ValueError('Prepared payload differs from frozen source')
                expected = hashlib.sha256(canonical(records[ordinal]).encode()).hexdigest()
                if envelope['record_hash'] != expected:
                    raise ValueError('Record hash mismatch')
                if envelope['source_id'] != records[ordinal].get(ENDPOINTS[endpoint]):
                    raise ValueError('Source ID differs from payload')
                if envelope['source_received_at'] != records[ordinal].get('received_at'):
                    raise ValueError('Source receipt differs from payload')
                if envelope['source_file'] != meta['source_file'] or envelope['source_file_sha256'] != meta['source_file_sha256']:
                    raise ValueError('Prepared source-file lineage differs')
                count += 1
        if count != meta['rows'] or count != len(records):
            raise ValueError('Frozen row count mismatch')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('setup', help='Add RAW objects and an object-scoped ingestion role')
    prepare = commands.add_parser('prepare', help='Freeze existing validated baseline and full users capture')
    prepare.add_argument('--baseline', default='data/analysis_snapshot_20261027')
    prepare.add_argument('--work', default='data/ingestion_work')
    prepare.add_argument('--sample', action='store_true')
    for name in ('verify', 'load', 'validate'):
        sub = commands.add_parser(name)
        sub.add_argument('snapshot')
    args = parser.parse_args()
    if args.command == 'prepare':
        path = freeze(args.baseline, args.work, args.sample)
        print(json.dumps({'snapshot': str(path), 'purpose': 'SMALL_TEST' if args.sample else 'FULL_BASELINE'}))
        return
    if args.command in {'load', 'verify', 'validate'}:
        manifest = verify_snapshot(args.snapshot)
        if args.command == 'verify':
            print(json.dumps({'snapshot_id': manifest['snapshot_id'], 'verified_rows': {k:v['rows'] for k,v in manifest['endpoints'].items()}}))
            return
    config = read_config()
    with connect(config) as connection:
        if args.command == 'setup':
            setup_raw(connection)
            role = setup_runtime_role(connection, config)
            print(json.dumps({'setup': 'complete', 'runtime_role': role}))
        elif args.command == 'load':
            result = load_snapshot(connection, args.snapshot, manifest)
            atomic_json(Path(args.snapshot) / 'load_result.json', {**result, 'validated_at': utc_now()})
            print(json.dumps(result))
        else:
            result = reconcile_notebook(connection, manifest)
            atomic_json(Path(args.snapshot) / 'reconciliation.json', {**result, 'validated_at': utc_now()})
            print(json.dumps(result, default=str))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never print connector errors containing credentials, URLs, or tokens.
        if isinstance(error, (ValueError, RuntimeError)):
            print(f'{type(error).__name__}: {error}', file=sys.stderr)
        else:
            print(json.dumps({'error_type':type(error).__name__, 'errno':getattr(error,'errno',None),
                              'sqlstate':getattr(error,'sqlstate',None), 'message':'Operation failed; details hidden'}), file=sys.stderr)
        raise SystemExit(1)
