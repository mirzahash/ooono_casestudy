"""Run isolated dbt with local .env; no credentials are written into the profile."""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'dbt'


def main():
    load_dotenv(ROOT / '.env')
    role = os.getenv('DBT_SNOWFLAKE_ROLE', 'OOONO_DBT')
    if role.upper() != 'OOONO_DBT':
        raise SystemExit('This project requires DBT_SNOWFLAKE_ROLE=OOONO_DBT; ACCOUNTADMIN is not a dbt runtime role.')
    password = os.getenv('SNOWFLAKE_PRIVATE_KEY_PASSWORD')
    if password:
        os.environ['DBT_ENV_SECRET_KEY_PASSPHRASE'] = password
    # Copy placeholders only; never interpolate credentials into YAML on disk.
    profile = PROJECT / 'profiles.yml'
    if not profile.exists():
        shutil.copyfile(PROJECT / 'profiles.yml.example', profile)
    executable = ROOT / '.venv-dbt/bin/dbt'
    if not executable.exists():
        raise SystemExit('Install requirements-dbt.txt in .venv-dbt first.')
    env = dict(os.environ, DBT_PROFILES_DIR=str(PROJECT), DBT_SEND_ANONYMOUS_USAGE_STATS='false')
    result = subprocess.run([str(executable), *sys.argv[1:], '--project-dir', str(PROJECT)], cwd=ROOT, env=env)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
