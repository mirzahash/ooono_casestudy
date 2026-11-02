"""Offline lifecycle checks: no history reload, safe resume, failed dbt checkpoint."""
import contextlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_pipeline as runner


class PipelineTests(unittest.TestCase):
    def execute(self, folder, previous=None, full=False, fail=False):
        calls = []
        class API:
            def extract(self, endpoint, directory, received_since=None):
                calls.append((endpoint, received_since))
                return {'pages': []}
        def build(command, **kwargs):
            target = Path(command[command.index('--target-path') + 1])
            target.mkdir(exist_ok=True)
            (target / 'run_results.json').write_text(json.dumps({'results':[{'status':'pass'}]}))
            return SimpleNamespace(returncode=int(fail))
        args = SimpleNamespace(run_dir=str(folder), full=full, since=None)
        with patch.object(runner, 'connect', return_value=contextlib.nullcontext(object())), \
             patch.object(runner, 'read_config', return_value={}), \
             patch.object(runner, 'last_success', return_value=previous), \
             patch.object(runner, 'EventsAPI', API), \
             patch.object(runner, 'prepare_load_files', return_value={}), \
             patch.object(runner, 'load_batch', return_value={'status':'RAW_LOADED'}) as load, \
             patch.object(runner, 'complete_run') as complete, \
             patch.object(runner.subprocess, 'run', side_effect=build):
            if fail:
                with self.assertRaisesRegex(RuntimeError, 'dbt failed'):
                    runner.pipeline(args)
            else:
                runner.pipeline(args)
            return calls, load.call_args.args[1], complete.call_count

    def test_normal_run_starts_at_successful_receipt_without_automatic_overlap(self):
        with tempfile.TemporaryDirectory() as folder:
            previous = {'receipt_cutoff':'2026-10-28T12:00:00+00:00'}
            calls, run, completed = self.execute(folder, previous)
            self.assertEqual(calls, [('drives',previous['receipt_cutoff']),
                                     ('warnings',previous['receipt_cutoff']),('users',None)])
            self.assertNotIn('parent_snapshot', run)
            self.assertEqual(completed, 1)

    def test_first_run_and_explicit_full_need_no_local_baseline(self):
        for full in [False, True]:
            with tempfile.TemporaryDirectory() as folder:
                calls, _, _ = self.execute(folder, full=full)
                self.assertTrue(all(since is None for _, since in calls))

    def test_failed_dbt_does_not_advance_success_and_resume_keeps_cutoff(self):
        with tempfile.TemporaryDirectory() as folder:
            _, before, completed = self.execute(folder, fail=True)
            self.assertEqual(completed, 0)
            _, after, completed = self.execute(folder)
            self.assertEqual(after['batch_id'], before['batch_id'])
            self.assertEqual(after['receipt_cutoff'], before['receipt_cutoff'])
            self.assertEqual(completed, 1)


if __name__ == '__main__':
    unittest.main()
