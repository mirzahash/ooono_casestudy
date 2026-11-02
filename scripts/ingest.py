"""Turn this extraction's pages into small, idempotent RAW load files."""
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

ENDPOINTS = {'drives': 'session_id', 'warnings': 'warning_id', 'users': 'user_id'}


def canonical(record):
    """Use consistent JSON text when comparing complete source reports."""
    return json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def prepare_records(records, endpoint, destination, batch_id, source_file):
    """Write only fetched records; never combine them with historical data.

    With no documented unique receipt ID, full payload + occurrence is our key.
    Seeing two identical copies again is idempotent; a third adds one report.
    A changed receipt or business field is preserved as a separate report.
    """
    seen = Counter()
    count = 0
    with gzip.open(destination, 'wt', encoding='utf-8') as output:
        for record in records:
            record_hash = hashlib.sha256(canonical(record).encode()).hexdigest()
            seen[record_hash] += 1
            report_key = hashlib.sha256(f'{record_hash}:{seen[record_hash]}'.encode()).hexdigest()
            row = {'report_key': report_key, 'record_hash': record_hash,
                   'source_id': record.get(ENDPOINTS[endpoint]),
                   'source_received_at': record.get('received_at'), 'payload': record,
                   'batch_id': batch_id, 'source_file': source_file}
            output.write(canonical(row) + '\n')
            count += 1
    return {'file': str(Path(destination).resolve()), 'rows': count}


def prepare_load_files(run_dir, batch_id, checkpoints):
    """Read saved response pages and prepare one compressed file per endpoint."""
    result = {}
    for endpoint, checkpoint in checkpoints.items():
        folder = run_dir / endpoint

        def records():
            for page in checkpoint['pages']:
                yield from json.loads((folder / page['file']).read_text())['data']

        result[endpoint] = prepare_records(
            records(), endpoint, run_dir / f'{endpoint}.json.gz', batch_id,
            folder.as_posix())
    return result
