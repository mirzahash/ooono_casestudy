"""Snowflake connection configuration. No warehouse writes occur here."""

import getpass
import os
import re
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTING_NAMES = ("ACCOUNT", "USER", "ROLE", "WAREHOUSE", "DATABASE", "SCHEMA")
AUTHENTICATORS = {"SNOWFLAKE_JWT", "externalbrowser", "username_password_mfa"}


def read_config():
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


def connect(config):
    import snowflake.connector

    options = dict(config)
    mode = options["authenticator"]
    if mode == "SNOWFLAKE_JWT":
        options["private_key_password"] = (
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


def quoted_identifier(value):
    """Only previously validated simple identifiers may enter SQL text."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", value):
        raise ValueError("Unsupported identifier")
    return '"' + value.upper() + '"'


def setup_raw(connection):
    """Only additive setup in the configured existing RAW schema."""
    sql = (PROJECT_ROOT / 'sql' / 'raw_setup.sql').read_text()
    sql = '\n'.join(line for line in sql.splitlines() if not line.lstrip().startswith('--'))
    with connection.cursor() as cursor:
        for statement in sql.split(';'):
            if statement.strip():
                cursor.execute(statement)


def setup_runtime_role(connection, config):
    """Small object-scoped loader role; the user object differs from LOGIN_NAME."""
    role = 'OOONO_INGESTOR'
    db, schema, wh = (quoted_identifier(config[k]) for k in ('database', 'schema', 'warehouse'))
    prefix = f'{db}.{schema}'
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE ROLE IF NOT EXISTS {role}')
        cursor.execute('SELECT CURRENT_USER()')
        user = '"' + cursor.fetchone()[0].replace('"', '""') + '"'
        cursor.execute(f'GRANT ROLE {role} TO USER {user}')
        cursor.execute(f'GRANT USAGE ON WAREHOUSE {wh} TO ROLE {role}')
        cursor.execute(f'GRANT USAGE ON DATABASE {db} TO ROLE {role}')
        cursor.execute(f'GRANT USAGE ON SCHEMA {prefix} TO ROLE {role}')
        # Needed only for session-local COPY landing tables.
        cursor.execute(f'GRANT CREATE TABLE ON SCHEMA {prefix} TO ROLE {role}')
        cursor.execute(f'GRANT READ, WRITE ON STAGE {prefix}.INGESTION_STAGE TO ROLE {role}')
        for table in ('DRIVES', 'WARNINGS', 'USERS'):
            cursor.execute(f'GRANT SELECT, INSERT ON TABLE {prefix}.{table} TO ROLE {role}')
        cursor.execute(f'GRANT SELECT, INSERT, UPDATE ON TABLE {prefix}.INGESTION_SNAPSHOTS TO ROLE {role}')
    return role


def load_snapshot(connection, directory, manifest):
    """COPY to temp landing then append using explicit snapshot/ordinal MERGEs."""
    import json
    import uuid

    snapshot_id = manifest['snapshot_id']
    if not re.fullmatch('[0-9a-f]{64}', snapshot_id):
        raise ValueError('Invalid snapshot ID')
    columns = ('SNAPSHOT_ID, SOURCE_ORDINAL, SOURCE_ID, SOURCE_RECEIVED_AT, PAYLOAD, '
               'RECORD_HASH, SOURCE_FILE, SOURCE_FILE_SHA256, INGESTED_AT')
    with connection.cursor() as cursor:
        cursor.execute('SELECT MANIFEST, STATUS FROM INGESTION_SNAPSHOTS WHERE SNAPSHOT_ID=%s', (snapshot_id,))
        existing = cursor.fetchall()
        if len(existing) > 1:
            raise ValueError('Duplicate warehouse snapshot manifest keys')
        if existing:
            stored = json.loads(existing[0][0]) if isinstance(existing[0][0], str) else existing[0][0]
            if stored != manifest:
                raise ValueError('Existing snapshot ID has a different manifest')
            if existing[0][1] != 'COMPLETE':
                raise ValueError('Unexpected incomplete manifest state')
            counts = validate_counts(cursor, manifest)
            return {'snapshot_id': snapshot_id, 'status': 'ALREADY_LOADED', 'counts': counts}
        landing = {}
        for endpoint, meta in manifest['endpoints'].items():
            if endpoint not in {'drives', 'warnings', 'users'}:
                raise ValueError('Unsupported endpoint')
            table = endpoint.upper()
            temp = 'LANDING_' + uuid.uuid4().hex.upper()
            landing[endpoint] = temp
            cursor.execute(f'CREATE TEMPORARY TABLE {temp} LIKE {table}')
            upload = (Path(directory) / meta['load_file']).resolve().as_uri().replace("'", "''")
            stage_path = f'@INGESTION_STAGE/{snapshot_id}/{endpoint}/'
            cursor.execute(f"PUT '{upload}' {stage_path} AUTO_COMPRESS=FALSE OVERWRITE=FALSE")
            cursor.fetchall()
            cursor.execute(f'''COPY INTO {temp} ({columns}) FROM (
                SELECT $1:snapshot_id::VARCHAR, $1:source_ordinal::NUMBER,
                       $1:source_id::VARCHAR, TRY_TO_TIMESTAMP_TZ($1:source_received_at::VARCHAR),
                       $1:payload, $1:record_hash::VARCHAR, $1:source_file::VARCHAR,
                       $1:source_file_sha256::VARCHAR, CURRENT_TIMESTAMP()
                FROM {stage_path}) FILE_FORMAT=(TYPE=JSON) ON_ERROR=ABORT_STATEMENT FORCE=FALSE''')
            cursor.fetchall()
            cursor.execute(f'SELECT COUNT(*), COUNT(DISTINCT SOURCE_ORDINAL), COUNT(DISTINCT SNAPSHOT_ID) FROM {temp}')
            total, unique, snapshots = cursor.fetchone()
            if total != meta['rows'] or unique != total or (total and snapshots != 1):
                raise ValueError(f'{endpoint}: landing row/key reconciliation failed')
            cursor.execute(f'SELECT COUNT(*) FROM {temp} WHERE SNAPSHOT_ID<>%s OR SOURCE_ORDINAL<0 OR SOURCE_ORDINAL>=%s', (snapshot_id, meta['rows']))
            if cursor.fetchone()[0]:
                raise ValueError('Landing snapshot or ordinal range differs')
            # A previous partial insertion is allowed only if every existing key agrees.
            cursor.execute(f'''SELECT COUNT(*) FROM {table} t JOIN {temp} s
                ON t.SNAPSHOT_ID=s.SNAPSHOT_ID AND t.SOURCE_ORDINAL=s.SOURCE_ORDINAL
                WHERE t.RECORD_HASH<>s.RECORD_HASH OR t.PAYLOAD<>s.PAYLOAD
                OR t.SOURCE_FILE_SHA256<>s.SOURCE_FILE_SHA256''')
            if cursor.fetchone()[0]:
                raise ValueError('Existing warehouse key has different content; refusing overwrite')
        cursor.execute('BEGIN')
        try:
            for endpoint, temp in landing.items():
                table = endpoint.upper()
                values = ', '.join('s.' + column.strip() for column in columns.split(','))
                cursor.execute(f'''MERGE INTO {table} t USING {temp} s
                    ON t.SNAPSHOT_ID=s.SNAPSHOT_ID AND t.SOURCE_ORDINAL=s.SOURCE_ORDINAL
                    WHEN NOT MATCHED THEN INSERT ({columns}) VALUES ({values})''')
                cursor.execute(f'''SELECT COUNT(*) FROM {temp} s LEFT JOIN {table} t
                    ON t.SNAPSHOT_ID=s.SNAPSHOT_ID AND t.SOURCE_ORDINAL=s.SOURCE_ORDINAL
                    WHERE t.SNAPSHOT_ID IS NULL OR t.RECORD_HASH<>s.RECORD_HASH OR t.PAYLOAD<>s.PAYLOAD
                    OR NOT EQUAL_NULL(t.SOURCE_ID,s.SOURCE_ID)
                    OR NOT EQUAL_NULL(t.SOURCE_RECEIVED_AT,s.SOURCE_RECEIVED_AT)
                    OR t.SOURCE_FILE<>s.SOURCE_FILE OR t.SOURCE_FILE_SHA256<>s.SOURCE_FILE_SHA256''')
                if cursor.fetchone()[0]:
                    raise ValueError(f'{endpoint}: warehouse payload/metadata integrity mismatch')
            counts = validate_counts(cursor, manifest)
            cursor.execute('''INSERT INTO INGESTION_SNAPSHOTS
                SELECT %s, PARSE_JSON(%s), 'COMPLETE', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()''',
                (snapshot_id, json.dumps(manifest)))
            cursor.execute('COMMIT')
        except Exception:
            cursor.execute('ROLLBACK')
            raise
        return {'snapshot_id': snapshot_id, 'status': 'LOADED', 'counts': counts,
                'integrity': 'All landing payloads, receipt metadata, hashes, ordinals and file lineage matched RAW'}


def validate_counts(cursor, manifest):
    counts = {}
    for endpoint, meta in manifest['endpoints'].items():
        if endpoint not in {'drives', 'warnings', 'users'}:
            raise ValueError('Unsupported endpoint')
        cursor.execute(f'''SELECT COUNT(*), COUNT(DISTINCT SOURCE_ORDINAL)
            FROM {endpoint.upper()} WHERE SNAPSHOT_ID=%s''', (manifest['snapshot_id'],))
        total, unique = cursor.fetchone()
        if total != meta['rows'] or total != unique:
            raise ValueError(f'{endpoint}: RAW count/ordinal reconciliation failed')
        counts[endpoint] = total
    return counts


def reconcile_notebook(connection, manifest):
    """Read-only CTEs reconcile the explicitly frozen baseline, not dbt models."""
    cutoff = manifest['identity']['analysis_receipt_cutoff_utc']
    if manifest['identity']['purpose'] != 'FULL_BASELINE' or cutoff != '2026-10-27T15:21:56.773109+00:00':
        raise ValueError('Notebook reference totals apply only to the approved full baseline cutoff')
    snapshot = manifest['snapshot_id']
    with connection.cursor() as cursor:
        counts = validate_counts(cursor, manifest)
        summaries = {}
        for endpoint in ('drives','warnings','users'):
            table = endpoint.upper()
            cursor.execute(f'''SELECT COUNT(*), COUNT_IF(SOURCE_ID IS NULL),
                COUNT_IF(PAYLOAD:received_at IS NOT NULL AND SOURCE_RECEIVED_AT IS NULL),
                COUNT(DISTINCT RECORD_HASH)
                FROM {table} WHERE SNAPSHOT_ID=%s''', (snapshot,))
            total, missing_id, invalid_receipt, distinct_hashes = cursor.fetchone()
            summaries[endpoint] = dict(rows=total, missing_ids=missing_id or 0,
                                       invalid_receipts=invalid_receipt or 0, distinct_record_hashes=distinct_hashes)
            if missing_id or invalid_receipt:
                raise ValueError(f'{endpoint}: unexpected missing identifiers/invalid receipts')
        base = '''WITH reports AS (
            SELECT *, PAYLOAD:session_id::VARCHAR AS SESSION_ID,
                TO_JSON(OBJECT_DELETE(PAYLOAD,'received_at')) AS BUSINESS_JSON
            FROM DRIVES WHERE SNAPSHOT_ID=%s AND SOURCE_RECEIVED_AT<=TO_TIMESTAMP_TZ(%s)
        ), identities AS (
            SELECT SESSION_ID, COUNT(*) AS REPORT_COUNT, COUNT(DISTINCT BUSINESS_JSON) AS BUSINESS_VERSIONS
            FROM reports GROUP BY SESSION_ID
        ), canonical AS (
            SELECT r.* FROM reports r JOIN identities i USING(SESSION_ID)
            WHERE i.BUSINESS_VERSIONS=1
            QUALIFY ROW_NUMBER() OVER (PARTITION BY r.SESSION_ID ORDER BY r.SOURCE_RECEIVED_AT,r.SOURCE_ORDINAL)=1
        )'''
        cursor.execute(base + ''' SELECT (SELECT COUNT(*) FROM reports), COUNT(*),
            (SELECT COUNT(*) FROM identities WHERE BUSINESS_VERSIONS>1) FROM canonical''', (snapshot,cutoff))
        drive_reports, sessions, conflicts = cursor.fetchone()
        if (drive_reports, sessions, conflicts) != (224194,219848,0):
            raise ValueError('Canonical drive reconciliation differs from notebook reference')
        cursor.execute('''SELECT COUNT(*),COUNT(DISTINCT SOURCE_ID) FROM WARNINGS
            WHERE SNAPSHOT_ID=%s AND SOURCE_RECEIVED_AT<=TO_TIMESTAMP_TZ(%s)''',(snapshot,cutoff))
        warnings, warning_ids = cursor.fetchone()
        if (warnings,warning_ids) != (315601,315601):
            raise ValueError('Warning reconciliation differs from notebook reference')
        cursor.execute('ALTER SESSION SET WEEK_START=1')
        cursor.execute(base + ''' SELECT DATE_TRUNC('WEEK',TRY_TO_TIMESTAMP_NTZ(PAYLOAD:started_at::VARCHAR))::DATE AS WEEK,
            COUNT(*) AS DRIVES, COUNT_IF(PAYLOAD:connection_count::NUMBER>1) AS MULTI
            FROM canonical
            WHERE TRY_TO_TIMESTAMP_NTZ(PAYLOAD:started_at::VARCHAR)>='2026-10-12'::TIMESTAMP_NTZ
              AND TRY_TO_TIMESTAMP_NTZ(PAYLOAD:started_at::VARCHAR)<'2026-10-26'::TIMESTAMP_NTZ
            GROUP BY WEEK ORDER BY WEEK''',(snapshot,cutoff))
        weeks = [{'week':str(row[0]),'eligible_drives':row[1],'multiple_connection_drives':row[2]} for row in cursor.fetchall()]
        expected = [{'week':'2026-10-12','eligible_drives':21711,'multiple_connection_drives':1519},
                    {'week':'2026-10-19','eligible_drives':21595,'multiple_connection_drives':1422}]
        if weeks != expected:
            raise ValueError('Weekly numerator/denominator differs from notebook reference')
        cursor.execute(base + ''' SELECT COUNT(*) FROM WARNINGS w JOIN canonical d
            ON w.SOURCE_ID IS NOT NULL AND w.PAYLOAD:session_id::VARCHAR=d.SESSION_ID
            WHERE w.SNAPSHOT_ID=%s AND w.SOURCE_RECEIVED_AT<=TO_TIMESTAMP_TZ(%s)''',
            (snapshot,cutoff,snapshot,cutoff))
        matched = cursor.fetchone()[0]
        if matched != 315449:
            raise ValueError('Canonical warning join differs from notebook reference')
        # Explicitly check duration/count eligibility rather than assuming all reports pass.
        cursor.execute(base + ''' SELECT COUNT(*) FROM canonical WHERE
            TRY_TO_TIMESTAMP_NTZ(PAYLOAD:started_at::VARCHAR) IS NULL
            OR TRY_TO_TIMESTAMP_NTZ(PAYLOAD:ended_at::VARCHAR) IS NULL
            OR TRY_TO_DOUBLE(PAYLOAD:duration_s::VARCHAR) IS NULL
            OR TRY_TO_DOUBLE(PAYLOAD:duration_s::VARCHAR)<=0
            OR TRY_TO_DOUBLE(PAYLOAD:connection_count::VARCHAR) IS NULL
            OR TRY_TO_DOUBLE(PAYLOAD:connection_count::VARCHAR)<1
            OR MOD(TRY_TO_DOUBLE(PAYLOAD:connection_count::VARCHAR),1)<>0
            OR DATEDIFF('SECOND',TRY_TO_TIMESTAMP_NTZ(PAYLOAD:started_at::VARCHAR),TRY_TO_TIMESTAMP_NTZ(PAYLOAD:ended_at::VARCHAR))<0
            OR ABS(TRY_TO_DOUBLE(PAYLOAD:duration_s::VARCHAR)-DATEDIFF('SECOND',TRY_TO_TIMESTAMP_NTZ(PAYLOAD:started_at::VARCHAR),TRY_TO_TIMESTAMP_NTZ(PAYLOAD:ended_at::VARCHAR)))>1''',
            (snapshot,cutoff))
        excluded = cursor.fetchone()[0]
        if excluded:
            raise ValueError('Unexpected metric eligibility exclusions')
    return {'snapshot_id':snapshot,'status':'RECONCILED','raw_counts':counts,'metadata':summaries,
            'analysis_receipt_cutoff_utc':cutoff,'drive_reports_by_cutoff':drive_reports,'canonical_sessions':sessions,
            'preserved_replay_rows_by_cutoff':drive_reports-sessions,'business_conflicts':conflicts,
            'warnings_by_cutoff':warnings,'matched_warnings':matched,'eligible_exclusions':excluded,'weeks':weeks}
