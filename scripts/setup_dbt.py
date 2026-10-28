"""One-time approved dbt grants, never used for routine transformations."""
from pathlib import Path
from dotenv import set_key
from snowflake_io import read_config, connect

config = read_config()
config['role'] = 'ACCOUNTADMIN'
with connect(config) as connection:
    with connection.cursor() as cursor:
        sql = Path('sql/dbt_setup.sql').read_text()
        sql = '\n'.join(line for line in sql.splitlines() if not line.lstrip().startswith('--'))
        for statement in sql.split(';'):
            if statement.strip(): cursor.execute(statement)
        cursor.execute('SELECT CURRENT_USER()')
        user = '"' + cursor.fetchone()[0].replace('"', '""') + '"'
        cursor.execute(f'GRANT ROLE OOONO_DBT TO USER {user}')
set_key('.env', 'DBT_SNOWFLAKE_ROLE', 'OOONO_DBT')
print('OOONO_DBT configured. Ingestion role and RAW records unchanged.')
