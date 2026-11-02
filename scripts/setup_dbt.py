"""One-time additive setup. Existing snapshot RAW tables are never changed."""
from pathlib import Path
from dotenv import set_key
from snowflake_io import read_config, connect, setup_raw, quoted_identifier, TABLES

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = read_config()
    config['role'] = 'ACCOUNTADMIN'
    database, warehouse = (quoted_identifier(config[k]) for k in ('database', 'warehouse'))
    with connect(config) as connection:
        setup_raw(connection)
        with connection.cursor() as cursor:
            cursor.execute(f'USE DATABASE {database}')
            for statement in (ROOT / 'sql/dbt_setup.sql').read_text().split(';'):
                if statement.strip():
                    cursor.execute(statement)
            cursor.execute('SELECT CURRENT_USER()')
            user = '"' + cursor.fetchone()[0].replace('"', '""') + '"'
            for role in ('OOONO_INGESTOR', 'OOONO_DBT'):
                cursor.execute(f'CREATE ROLE IF NOT EXISTS {role}')
                cursor.execute(f'GRANT ROLE {role} TO USER {user}')
                cursor.execute(f'GRANT USAGE ON WAREHOUSE {warehouse} TO ROLE {role}')
                cursor.execute(f'GRANT USAGE ON DATABASE {database} TO ROLE {role}')
                cursor.execute(f'GRANT USAGE ON SCHEMA {database}.RAW TO ROLE {role}')
                for table in [*TABLES.values(), 'INGESTION_RUNS']:
                    cursor.execute(f'GRANT SELECT ON TABLE {database}.RAW.{table} TO ROLE {role}')
            cursor.execute(f'GRANT CREATE TABLE ON SCHEMA {database}.RAW TO ROLE OOONO_INGESTOR')
            cursor.execute(f'GRANT READ, WRITE ON STAGE {database}.RAW.REPORT_LOAD_STAGE TO ROLE OOONO_INGESTOR')
            for table in TABLES.values():
                cursor.execute(f'GRANT INSERT ON TABLE {database}.RAW.{table} TO ROLE OOONO_INGESTOR')
            cursor.execute(f'GRANT DELETE ON TABLE {database}.RAW.USER_PROFILES TO ROLE OOONO_INGESTOR')
            cursor.execute(f'GRANT INSERT, UPDATE ON TABLE {database}.RAW.INGESTION_RUNS TO ROLE OOONO_INGESTOR')
            for schema in ('STAGING', 'ANALYTICS'):
                cursor.execute(f'GRANT USAGE, CREATE TABLE, CREATE VIEW ON SCHEMA {database}.{schema} TO ROLE OOONO_DBT')
            # The reader role exists before dbt reapplies its configured SELECT grant.
            cursor.execute('CREATE ROLE IF NOT EXISTS STEEP_READONLY')
            cursor.execute(f'GRANT USAGE ON WAREHOUSE {warehouse} TO ROLE STEEP_READONLY')
            cursor.execute(f'GRANT USAGE ON DATABASE {database} TO ROLE STEEP_READONLY')
            cursor.execute(f'GRANT USAGE ON SCHEMA {database}.ANALYTICS TO ROLE STEEP_READONLY')
    set_key(str(ROOT / '.env'), 'DBT_SNOWFLAKE_ROLE', 'OOONO_DBT')
    print('Additive RAW and role setup complete; no event data changed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(f'Setup failed ({type(error).__name__}); check permissions and local configuration.') from None
