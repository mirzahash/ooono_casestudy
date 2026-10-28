"""Fresh workflow invariants: overlap preserves receipts, checkpoints require success."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_pipeline import merge_overlap, publish_success


class RefreshTests(unittest.TestCase):
    def test_overlap_does_not_collapse_distinct_receipts_or_source_multiplicity(self):
        first={'session_id':'A','received_at':'2026-10-27T10:00:00Z','connection_count':2}
        repeated={'session_id':'A','received_at':'2026-10-27T10:01:00Z','connection_count':2}
        changed={'session_id':'A','received_at':'2026-10-27T10:00:00Z','connection_count':3}
        parent=[first,first,repeated]
        delta=[first,first,first,repeated,changed]
        result=merge_overlap(parent,delta)
        self.assertEqual(result.count(first),3)
        self.assertEqual(result.count(repeated),1)
        self.assertEqual(result.count(changed),1)
        self.assertEqual(merge_overlap(result,delta),result)

    def test_missing_records_or_empty_delta_do_not_erase_parent(self):
        parent=[{'session_id':'A'},{'session_id':'B'}]
        self.assertEqual(merge_overlap(parent,[]),parent)
        self.assertEqual(merge_overlap(parent,[parent[0]]),parent)

    def test_failed_or_older_run_cannot_advance_successful_cutoff(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            complete={'status':'COMPLETE','snapshot':'data/snapshots/a','snapshot_id':'a',
                      'receipt_cutoff':'2026-10-28T12:00:00+00:00','completed_at':'2026-10-28T12:01:00+00:00'}
            publish_success(complete,path)
            expected=json.loads(path.read_text())
            with self.assertRaises(ValueError):
                publish_success({**complete,'status':'DBT_FAILED','receipt_cutoff':'2026-10-29T12:00:00+00:00'},path)
            self.assertEqual(json.loads(path.read_text()),expected)
            publish_success({**complete,'receipt_cutoff':'2026-10-27T12:00:00+00:00'},path)
            self.assertEqual(json.loads(path.read_text()),expected)


if __name__=='__main__':unittest.main()
