"""Connect to Snowflake and insert newly observed reports into append-only RAW."""

import getpass
import os
import re
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTING_NAMES = ("ACCOUNT", "USER", "ROLE", "WAREHOUSE", "DATABASE", "SCHEMA")
AUTHENTICATORS = {"SNOWFLAKE_JWT", "externalbrowser", "username_password_mfa"}


# Read and check local Snowflake settings before connecting.
def read_config():
    """Read/validate local Snowflake environment settings without connecting."""
    load_dotenv(PROJECT_ROOT / ".env")
    config = {
        name.lower(): os.environ.get(f"SNOWFLAKE_{name}", "").strip()
        for name in SETTING_NAMES
    }
    missing = [f"SNOWFLAKE_{name.upper()}" for name, value in config.items() if not value]
    if missing:
        raise ValueError("Missing local configuration: " + ", ".join(missing))
    for name in ("role", "warehouse", "database", "schema"):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", config[name]):
            raise ValueError(f"{name}: this MVP requires a simple unquoted Snowflake identifier")
    mode = os.environ.get("SNOWFLAKE_AUTHENTICATOR", "SNOWFLAKE_JWT").strip()
    if mode not in AUTHENTICATORS:
        raise ValueError("Unsupported SNOWFLAKE_AUTHENTICATOR")
    config["authenticator"] = mode
    if mode == "SNOWFLAKE_JWT":
        key_file = os.environ.get("SNOWFLAKE_PRIVATE_KEY_FILE", "").strip()
        if not key_file:
            raise ValueError("Set SNOWFLAKE_PRIVATE_KEY_FILE to your encrypted PKCS8 key")
        key_path = Path(key_file).expanduser()
        if not key_path.is_absolute():
            key_path = PROJECT_ROOT / key_path
        if not key_path.is_file():
            raise ValueError("The configured private key file does not exist")
        if b"BEGIN ENCRYPTED PRIVATE KEY" not in key_path.read_bytes():
            raise ValueError("An encrypted PKCS8 private key is required")
        config["private_key_file"] = str(key_path.resolve())
    return config


# Sign in to Snowflake using the supplied settings.
def connect(config):
    """Authenticate from config and return an open Snowflake connector connection."""
    import snowflake.connector

    # Copy rather than mutate config when adding sensitive authentication options.
    # The returned connection is live; callers must scope/close it appropriately.
    options = dict(config)
    mode = options["authenticator"]
    if mode == "SNOWFLAKE_JWT":
        options["private_key_file_pwd"] = (
            os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSWORD")
            or getpass.getpass("Snowflake private-key passphrase: ")
        )
    elif mode == "username_password_mfa":
        options["password"] = getpass.getpass("Snowflake password (not saved): ")
    options.update(
        login_timeout=60,
        network_timeout=60,
        enable_server_session_keep_alive_auto_detection=False,
        session_parameters={"TIMEZONE": "UTC", "QUERY_TAG": "ooono_case_connectivity"},
    )
    return snowflake.connector.connect(**options)


# Check and quote a Snowflake object name before putting it into SQL.
def quoted_identifier(value):
    """Return a validated simple SQL identifier, uppercased and double quoted."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", value):
        raise ValueError("Unsupported identifier")
    return '"' + value.upper() + '"'


# Create any missing RAW tables and the upload stage.
def setup_raw(connection):
    """Execute additive RAW DDL using an already configured connection/schema."""
    sql = (PROJECT_ROOT / 'sql' / 'raw_setup.sql').read_text()
    sql = '\n'.join(line for line in sql.splitlines() if not line.lstrip().startswith('--'))
    with connection.cursor() as cursor:
        for statement in sql.split(';'):
            if statement.strip():
                cursor.execute(statement)


TABLES = {'drives': 'DRIVE_REPORTS', 'warnings': 'WARNING_REPORTS', 'users': 'USER_PROFILES'}


def last_success(connection):
    """The warehouse checkpoint works on a new laptop too; no local state needed."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT BATCH_ID, RECEIPT_CUTOFF FROM INGESTION_RUNS "
                       "WHERE STATUS='COMPLETE' ORDER BY RECEIPT_CUTOFF DESC LIMIT 1")
        row = cursor.fetchone()
    return {'batch_id': row[0], 'receipt_cutoff': row[1].isoformat()} if row else None


def load_batch(connection, run, files):
    """Validate fetched files, insert unseen reports, and replace current users.

    A batch's inserts and RAW_LOADED record commit together. Replaying it is safe.
    This assumes one pipeline writer, not distributed exactly-once delivery.
    """
    import uuid
    if not re.fullmatch(r'[0-9a-f]{64}', run['batch_id']):
        raise ValueError('Invalid batch ID')
    if set(files) != set(TABLES):
        raise ValueError('A batch must contain all three endpoints')
    with connection.cursor() as cursor:
        latest = last_success(connection)
        from datetime import datetime
        if latest and datetime.fromisoformat(latest['receipt_cutoff']) > datetime.fromisoformat(run['receipt_cutoff']):
            raise ValueError('A newer run has completed; do not replay older data over it')
        cursor.execute('SELECT STATUS FROM INGESTION_RUNS WHERE BATCH_ID=%s', (run['batch_id'],))
        existing = cursor.fetchall()
        if len(existing) > 1:
            raise ValueError('Duplicate batch registry keys')
        if existing:
            return {'status': 'ALREADY_LOADED', 'batch_id': run['batch_id']}
        landing = {}
        for endpoint, meta in files.items():
            table = TABLES[endpoint]
            temp = 'LANDING_' + uuid.uuid4().hex.upper()
            landing[endpoint] = temp
            cursor.execute(f'CREATE TEMPORARY TABLE {temp} LIKE {table}')
            # PUT expects the literal local path, not URL escapes such as %3D for '='.
            upload = ('file://' + Path(meta['file']).resolve().as_posix()).replace("'", "''")
            stage = f"@REPORT_LOAD_STAGE/{run['batch_id']}/{endpoint}/"
            cursor.execute(f"PUT '{upload}' {stage} AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
            cursor.fetchall()
            cursor.execute(f'''COPY INTO {temp} FROM (
                SELECT $1:report_key::VARCHAR, $1:source_id::VARCHAR,
                    TRY_TO_TIMESTAMP_TZ($1:source_received_at::VARCHAR), $1:payload,
                    $1:record_hash::VARCHAR, $1:batch_id::VARCHAR, $1:source_file::VARCHAR,
                    CURRENT_TIMESTAMP() FROM {stage}
            ) FILE_FORMAT=(TYPE=JSON) ON_ERROR=ABORT_STATEMENT''')
            cursor.fetchall()
            cursor.execute(f'SELECT COUNT(*), COUNT(DISTINCT REPORT_KEY), COUNT_IF(SOURCE_ID IS NULL) FROM {temp}')
            total, unique, missing = cursor.fetchone()
            if total != meta['rows'] or unique != total or missing:
                raise ValueError(f'{endpoint}: invalid landing counts, keys or IDs')
            cursor.execute(f'SELECT COUNT(*) FROM {temp} WHERE BATCH_ID<>%s OR REPORT_KEY IS NULL OR RECORD_HASH IS NULL OR SOURCE_FILE IS NULL', (run['batch_id'],))
            if cursor.fetchone()[0]:
                raise ValueError('Landing batch metadata is invalid')
            if endpoint != 'users':
                cursor.execute(f'SELECT COUNT(*) FROM {temp} WHERE SOURCE_RECEIVED_AT IS NULL')
                if cursor.fetchone()[0]:
                    raise ValueError(f'{endpoint}: missing/invalid receipt timestamps')
            # A hash key must never silently replace different contents.
            cursor.execute(f'''SELECT COUNT(*) FROM {table} t JOIN {temp} s USING(REPORT_KEY)
                WHERE t.PAYLOAD <> s.PAYLOAD OR t.RECORD_HASH <> s.RECORD_HASH''')
            if cursor.fetchone()[0]:
                raise ValueError('Existing report key has different contents')
        cursor.execute('BEGIN')
        try:
            inserted = {}
            for endpoint, temp in landing.items():
                table = TABLES[endpoint]
                if endpoint == 'users':
                    # Users are a full current-state capture, not an event stream.
                    cursor.execute(f'DELETE FROM {table}')
                    cursor.execute(f'INSERT INTO {table} SELECT * FROM {temp}')
                else:
                    cursor.execute(f'''MERGE INTO {table} t USING {temp} s
                        ON t.REPORT_KEY=s.REPORT_KEY
                        WHEN NOT MATCHED THEN INSERT
                        (REPORT_KEY,SOURCE_ID,SOURCE_RECEIVED_AT,PAYLOAD,RECORD_HASH,BATCH_ID,SOURCE_FILE,INGESTED_AT)
                        VALUES (s.REPORT_KEY,s.SOURCE_ID,s.SOURCE_RECEIVED_AT,s.PAYLOAD,
                                s.RECORD_HASH,s.BATCH_ID,s.SOURCE_FILE,s.INGESTED_AT)''')
                inserted[endpoint] = cursor.rowcount
                cursor.execute(f'''SELECT COUNT(*) FROM {temp} s LEFT JOIN {table} t USING(REPORT_KEY)
                    WHERE t.REPORT_KEY IS NULL OR t.PAYLOAD <> s.PAYLOAD
                    OR NOT EQUAL_NULL(t.SOURCE_RECEIVED_AT,s.SOURCE_RECEIVED_AT)''')
                if cursor.fetchone()[0]:
                    raise ValueError('RAW contents do not match landing records')
            cursor.execute('''INSERT INTO INGESTION_RUNS
                SELECT %s,TO_TIMESTAMP_TZ(%s),TO_TIMESTAMP_TZ(%s),'RAW_LOADED',CURRENT_TIMESTAMP(),NULL''',
                (run['batch_id'], run['receipt_cutoff'], run['received_since']))
            cursor.execute('COMMIT')
        except Exception:
            cursor.execute('ROLLBACK')
            raise
    return {'status': 'RAW_LOADED', 'batch_id': run['batch_id'], 'inserted_rows': inserted}


def complete_run(connection, batch_id):
    """Advance the warehouse checkpoint only after dbt models and tests succeed."""
    with connection.cursor() as cursor:
        cursor.execute("UPDATE INGESTION_RUNS SET STATUS='COMPLETE',COMPLETED_AT=CURRENT_TIMESTAMP() "
                       "WHERE BATCH_ID=%s", (batch_id,))
