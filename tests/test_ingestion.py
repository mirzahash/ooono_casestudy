"""Focused invariants: pagination checkpoints, immutable inputs, receipt preservation."""
import gzip
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from api import EventsAPI
from ingest import verify_snapshot

TEST_SNAPSHOT = Path('data/snapshots/215eb2d18dd04f006286cc90a97ad13fe6086d6714ffcd405656b858b0c4e402')


class FakeAPI(EventsAPI):
    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []

    def get(self, endpoint, params):
        self.calls.append(dict(params))
        payload = next(self.pages)
        return SimpleNamespace(json=lambda: payload, content=json.dumps(payload).encode())


class PaginationTests(unittest.TestCase):
    def test_short_page_follows_cursor_and_completed_resume_has_no_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            api = FakeAPI([{'data':[{'id':1}], 'next_cursor':'next'},
                           {'data':[], 'next_cursor':None}])
            result = api.extract('users', directory)
            self.assertTrue(result['complete'])
            self.assertEqual(len(api.calls), 2)
            self.assertEqual(api.calls[1]['cursor'], 'next')
            api.extract('users', directory)
            self.assertEqual(len(api.calls), 2)
            Path(directory, 'page_00000.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                api.extract('users', directory)

    def test_scope_change_and_repeated_cursor_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            api = FakeAPI([{'data':[], 'next_cursor':'same'}, {'data':[], 'next_cursor':'same'}])
            with self.assertRaisesRegex(ValueError, 'Repeated cursor'):
                api.extract('drives', directory, received_since='2026-10-01T00:00:00Z')
            with self.assertRaisesRegex(ValueError, 'scope'):
                api.extract('drives', directory, received_since='2026-10-02T00:00:00Z')

    def test_page_guard_never_marks_partial_extract_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            api = FakeAPI([{'data':[], 'next_cursor':'next'}])
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                api.extract('warnings', directory, max_pages=1)
            self.assertFalse(json.loads(Path(directory, 'checkpoint.json').read_text())['complete'])


@unittest.skipUnless(TEST_SNAPSHOT.exists(), 'Local frozen test snapshot is not distributed with the repo')
class SnapshotTests(unittest.TestCase):
    def test_repeated_source_receipts_survive_as_separate_ordinals(self):
        manifest = verify_snapshot(TEST_SNAPSHOT)
        with gzip.open(TEST_SNAPSHOT / manifest['endpoints']['drives']['load_file'], 'rt') as stream:
            rows = [json.loads(line) for line in stream]
        self.assertEqual(len({r['source_ordinal'] for r in rows}), len(rows))
        self.assertLess(len({r['source_id'] for r in rows}), len(rows))

    def test_changed_source_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / 'snapshot'
            shutil.copytree(TEST_SNAPSHOT, copy)
            with (copy / 'sources/drives.json').open('a') as stream:
                stream.write(' ')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                verify_snapshot(copy)


if __name__ == '__main__':
    unittest.main()
