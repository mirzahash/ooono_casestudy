"""Pagination recovery, stable report keys and RAW transaction safety."""
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from api import EventsAPI
from ingest import prepare_records



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


class ReportKeyTests(unittest.TestCase):
    def write(self, directory, records, batch):
        path = Path(directory) / (batch + '.gz')
        prepare_records(records, 'drives', path, batch, 'saved/pages')
        with gzip.open(path, 'rt') as stream:
            return [json.loads(line) for line in stream]

    def test_keys_are_stable_across_batches_and_changed_receipts_are_preserved(self):
        first = {'session_id':'A', 'received_at':'2026-10-27T10:00:00Z', 'connection_count':2}
        repeat = {**first, 'received_at':'2026-10-27T10:01:00Z'}
        conflict = {**first, 'connection_count':3}
        with tempfile.TemporaryDirectory() as folder:
            a = self.write(folder, [first, first, repeat], 'a')
            b = self.write(folder, [first, first, first, repeat, conflict], 'b')
            akeys = {r['report_key'] for r in a}
            bkeys = {r['report_key'] for r in b}
            self.assertEqual(len(akeys), 3)
            self.assertEqual(len(bkeys - akeys), 2)
            self.assertEqual([r['payload'] for r in b], [first,first,first,repeat,conflict])

    def test_only_incoming_records_are_written_and_empty_batch_is_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(self.write(folder, [], 'empty'), [])
            row = self.write(folder, [{'session_id':'new'}], 'new')
            self.assertEqual(len(row), 1)
            self.assertEqual(row[0]['source_id'], 'new')

class RawLoadTests(unittest.TestCase):
    def test_invalid_batch_id_is_rejected_before_database_work(self):
        from unittest.mock import Mock
        from snowflake_io import load_batch
        connection = Mock()
        with self.assertRaisesRegex(ValueError, 'batch ID'):
            load_batch(connection, {'batch_id':"bad'; SQL"}, {})
        connection.cursor.assert_not_called()

    def test_missing_endpoint_is_rejected_before_database_work(self):
        from unittest.mock import Mock
        from snowflake_io import load_batch
        connection = Mock()
        with self.assertRaisesRegex(ValueError, 'three endpoints'):
            load_batch(connection, {'batch_id':'a'*64}, {})
        connection.cursor.assert_not_called()

    def test_registry_failure_rolls_back_report_inserts(self):
        from unittest.mock import MagicMock, patch
        from snowflake_io import load_batch
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []
        def fetchone():
            if 'COUNT(DISTINCT REPORT_KEY)' in cursor.execute.call_args.args[0]:
                return (1, 1, 0)
            return (0,)
        cursor.fetchone.side_effect = fetchone
        def execute(sql, *args):
            if 'INSERT INTO INGESTION_RUNS' in sql:
                raise RuntimeError('simulated registry failure')
        cursor.execute.side_effect = execute
        files = {ep:{'file':'/tmp/example.json.gz','rows':1} for ep in ['drives','warnings','users']}
        run = {'batch_id':'a'*64,'receipt_cutoff':'2026-10-30T00:00:00+00:00','received_since':None}
        with patch('snowflake_io.last_success', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'registry failure'):
                load_batch(connection, run, files)
        statements = [c.args[0] for c in cursor.execute.call_args_list]
        self.assertIn('BEGIN', statements)
        self.assertIn('ROLLBACK', statements)
        self.assertNotIn('COMMIT', statements)


    def test_put_preserves_equals_and_spaces_in_local_filename(self):
        from unittest.mock import MagicMock, patch
        from snowflake_io import load_batch
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []
        statements = []
        def execute(sql, *args):
            statements.append(sql)
            if sql.startswith('PUT '):
                raise RuntimeError('stop after inspecting upload')
        cursor.execute.side_effect = execute
        path = Path('/tmp/extraction_date=2026-11-03/a run/drives.json.gz')
        files = {ep:{'file':str(path),'rows':1} for ep in ['drives','warnings','users']}
        run = {'batch_id':'a'*64,'receipt_cutoff':'2026-11-03T00:00:00+00:00','received_since':None}
        with patch('snowflake_io.last_success', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'stop after inspecting'):
                load_batch(connection, run, files)
        upload = next(sql for sql in statements if sql.startswith('PUT '))
        self.assertIn('file://' + path.resolve().as_posix(), upload)
        self.assertNotIn('%3D', upload)
        self.assertNotIn('%20', upload)


if __name__ == '__main__':
    unittest.main()
