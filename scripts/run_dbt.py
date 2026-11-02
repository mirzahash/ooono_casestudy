"""Run dbt in its isolated environment with credentials kept outside Git."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from dotenv import load_dotenv
from snowflake_io import connect, read_config, last_success

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'dbt'


def main():
    load_dotenv(ROOT / '.env')
    role = os.getenv('DBT_SNOWFLAKE_ROLE', 'OOONO_DBT')
    if role.upper() != 'OOONO_DBT':
        raise SystemExit('Routine dbt execution requires OOONO_DBT')
    if os.getenv('SNOWFLAKE_PRIVATE_KEY_PASSWORD'):
        os.environ['DBT_ENV_SECRET_KEY_PASSPHRASE'] = os.environ['SNOWFLAKE_PRIVATE_KEY_PASSWORD']
    if not (PROJECT / 'profiles.yml').exists():
        shutil.copyfile(PROJECT / 'profiles.yml.example', PROJECT / 'profiles.yml')
    arguments = sys.argv[1:]
    if arguments and arguments[0] in {'build', 'run', 'test'} and not any(
            arg == '--vars' or arg.startswith('--vars=') for arg in arguments):
        # Standalone builds use the last successful warehouse run, not a hardcoded date.
        config = read_config()
        config['role'] = role
        with connect(config) as connection:
            run = last_success(connection)
        if not run:
            raise SystemExit('No successful ingestion yet. Run scripts/run_pipeline.py first.')
        arguments += ['--vars', json.dumps({'run_id': run['batch_id'], 'receipt_cutoff': run['receipt_cutoff']})]
    env = dict(os.environ, DBT_PROFILES_DIR=str(PROJECT), DBT_SEND_ANONYMOUS_USAGE_STATS='false')
    return subprocess.run([str(ROOT / '.venv-dbt/bin/dbt'), *arguments,
                           '--project-dir', str(PROJECT)], cwd=ROOT, env=env).returncode


if __name__ == '__main__':
    raise SystemExit(main())
