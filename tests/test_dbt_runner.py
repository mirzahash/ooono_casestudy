"""The wrapper selects a successful cutoff only when no explicit vars are given."""
import contextlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_dbt


class DbtRunnerTests(unittest.TestCase):
    def test_standalone_build_uses_successful_warehouse_cutoff(self):
        with patch.object(run_dbt, 'load_dotenv'), \
             patch.object(run_dbt, 'read_config', return_value={}), \
             patch.object(run_dbt, 'connect', return_value=contextlib.nullcontext(object())), \
             patch.object(run_dbt, 'last_success', return_value={'batch_id':'a'*64,'receipt_cutoff':'2026-10-30T00:00:00+00:00'}), \
             patch.object(run_dbt.sys, 'argv', ['run_dbt.py','build']), \
             patch.object(run_dbt.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as launch:
            self.assertEqual(run_dbt.main(), 0)
            command = launch.call_args.args[0]
            variables = json.loads(command[command.index('--vars')+1])
            self.assertEqual(variables['run_id'], 'a'*64)
            self.assertEqual(variables['receipt_cutoff'], '2026-10-30T00:00:00+00:00')

    def test_explicit_pipeline_vars_do_not_select_a_different_run(self):
        with patch.object(run_dbt, 'load_dotenv'), \
             patch.object(run_dbt, 'last_success') as lookup, \
             patch.object(run_dbt.sys, 'argv', ['run_dbt.py','build','--vars','{"run_id":"candidate"}']), \
             patch.object(run_dbt.subprocess, 'run', return_value=SimpleNamespace(returncode=1)):
            self.assertEqual(run_dbt.main(), 1)
            lookup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
