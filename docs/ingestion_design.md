# Implemented RAW ingestion architecture

Status: connectivity, additive RAW setup, a small test and rerun, the complete
snapshot load, and notebook reconciliation have passed. No dbt or Steep work has
started. See `reports/raw_validation.md` for counts and validation evidence.

## Connection

Use Snowflake Python Connector 5.1.0 with encrypted key-pair authentication.
`SNOWFLAKE_USER` must contain the actual LOGIN_NAME, not the Snowflake user object's
name. The initial browser attempt failed because connector SAML SSO was not
configured; Google login to Snowsight is separate from this Python authentication.
The registered public key is paired with an encrypted private key under ignored
`data/snowflake_auth/`. Its passphrase remains in ignored `.env`.

The existing `OOONO_WH`, `OOONO_CASE`, and `RAW` schema were verified and reused.
ACCOUNTADMIN was used only for initial setup. Runtime loads now use OOONO_INGESTOR,
with usage on the configured warehouse/database/schema, READ/WRITE on the internal
stage, SELECT/INSERT on RAW event tables, and SELECT/INSERT/UPDATE on the snapshot
manifest. CREATE TABLE on RAW permits session-local landing tables. The warehouse
configuration was reused without changing it.

## Flow and files

```text
Validated frozen drive/warning baseline + complete users API response pages
  -> immutable JSON files and content-addressed manifest
  -> gzip NDJSON envelopes
  -> Snowflake internal stage (PUT)
  -> temporary landing tables (COPY)
  -> transactional append-only MERGEs into RAW + completed snapshot manifest
  -> read-only reconciliation against notebook 04
```

```text
scripts/api.py               OAuth, bounded retries, checkpointed complete page bodies
scripts/ingest.py            prepare, verify, setup, load, validate commands
scripts/snowflake_io.py      connection, additive setup, scoped role, COPY/MERGE, reconciliation
scripts/check_snowflake.py   read-only connection/object checks
sql/raw_setup.sql            additive RAW tables and internal stage
 tests/test_ingestion.py     pagination, corruption, and preserved-receipt invariants
```

Local-only immutable inputs are under `data/snapshots/<snapshot_id>/`. Each has
original source files, preserved users response pages, gzip load files, and a
manifest. Checkpoints are outside the frozen snapshots. Load and reconciliation
results are sidecars; they do not change the immutable identity/source files.

## RAW schemas

`OOONO_CASE.RAW.DRIVES`, `.WARNINGS`, and `.USERS` share this envelope:

| Column | Type | Meaning |
| --- | --- | --- |
| SNAPSHOT_ID | VARCHAR NOT NULL | Content-addressed extraction batch identity |
| SOURCE_ORDINAL | NUMBER(38,0) NOT NULL | Zero-based position in the frozen endpoint record array |
| SOURCE_ID | VARCHAR | session_id, warning_id, or user_id, respectively |
| SOURCE_RECEIVED_AT | TIMESTAMP_TZ | Source received_at, null when absent (users) |
| PAYLOAD | VARIANT NOT NULL | Entire original source record, including timestamp strings and nulls |
| RECORD_HASH | VARCHAR(64) NOT NULL | SHA-256 of canonical JSON of the full record, including receipt |
| SOURCE_FILE | VARCHAR NOT NULL | Snapshot-relative original source file |
| SOURCE_FILE_SHA256 | VARCHAR(64) NOT NULL | Original source file checksum |
| INGESTED_AT | TIMESTAMP_TZ NOT NULL | Warehouse landing/load time, not a source receipt time |

`RAW.INGESTION_SNAPSHOTS` contains SNAPSHOT_ID, MANIFEST (VARIANT), STATUS,
LOAD_STARTED_AT, and LOAD_COMPLETED_AT. Only successfully committed batches have
a COMPLETE row. Original source bytes and checksums preserve file fidelity;
VARIANT preserves JSON semantics rather than original whitespace/key ordering.
Initial manifest timestamps were recorded when the load transaction completed;
per-row INGESTED_AT records the actual earlier COPY processing time.

## Three different identities

- **Source receipt:** an observed report. Drives expose session_id, but no separate
  documented receipt ID. Warnings expose warning_id, without a separate documented
  repeated-receipt identifier or guarantee of receipt uniqueness.
- **Snapshot:** the immutable extraction batch. Identity hashes file checksums,
  endpoint counts, receipt/capture cutoffs, purpose, and format version.
- **Canonical session:** a business session derived later by agreement checks on
  session_id. This is not a RAW key and ingestion does not collapse it.

## Idempotency and preservation

Reruns key on `(SNAPSHOT_ID, SOURCE_ORDINAL)`. Local verification checks file hashes,
source payload equality, record hashes, metadata, and sequential ordinals. COPY
loads session-local landing tables; a MERGE only inserts unmatched RAW keys.
A matching key with different content causes an error. Every loaded payload,
source ID, receipt, hash, ordinal, and file lineage is compared to its landing row
before committing. Target count and ordinal uniqueness are also reconciled.

All three RAW MERGEs and the completed manifest are committed in one DML transaction;
DDL/COPY happen before it. Failure rolls back the transaction. A matching completed
snapshot returns ALREADY_LOADED and verifies counts. Single-writer execution is an
explicit MVP assumption; ordinary Snowflake uniqueness constraints are not relied
on for enforcement. RAW is never truncated, replaced, or business-deduplicated.

Different snapshots may contain the same API record. Equal full-record hashes can
flag this overlap; they cannot prove the identity of a physical delivery when
identical receipts share timestamp precision/content. Different receipt timestamps
or payloads remain distinct. Cross-snapshot deduplication is not implemented in RAW.
Downstream processing must select the intended complete snapshot/delta lineage,
not sum every snapshot. The small test remains in RAW under a separate SMALL_TEST
snapshot; production validation selects FULL_BASELINE explicitly.

## Incremental extraction support and limits

API version 1.4 documents `received_since` on drives and warnings. Users have no
receipt filter and require complete current-state captures. Cursors paginate a
particular query; permanence, expiry, snapshot isolation, and use as continuous
incremental offsets are undocumented. A cursor is not a successful-load watermark.

`api.py` supports received_since and checkpointed paging. `scripts/run_pipeline.py`
now implements the minimal local receipt-cutoff checkpoint, overlap extraction,
cumulative snapshot assembly, append-only load, and explicit dbt build. The older
`ingest.py prepare` remains available for importing the validated baseline plus users.
No production scheduler or generalized incremental framework is implemented. Future daily delta batches should use the last successful
receipt cutoff with a 24-hour overlap, freeze the response pages, load append-only,
and advance the watermark only after a complete successful load. Preserve overlap
rows in their snapshot lineage; later transformations identify overlap as distinct
from business deduplication. Backdated receipts outside the window and source
deletions require periodic full reconciliation; they are not guaranteed captured.

Requests have connect/read timeouts, four bounded GET attempts for transient
network/429/5xx errors, backoff/jitter, Retry-After, and one token renewal on 401.
Every page is atomically checkpointed with its next cursor. Short pages are not
assumed final. A repeated cursor, malformed envelope, changed request scope,
checksum mismatch, or 2,000-page guard fails clearly and prevents completion.
Invalid saved cursors must be handled with a separate new extraction, not an
untracked restart appended to an old snapshot. API credentials/tokens are not logged.

## Frozen baseline and reproducibility

The active profiling cache had become incomplete. The completed baseline and
completed 27 October delta reconstructed `data/analysis_snapshot_20261027/`
offline, with source/reconstruction hashes; no drive/warning re-extraction was
needed. The loaded FULL_BASELINE copies those exact reconstructed bytes.

The inherited baseline retains all cached records, not the original historical
HTTP envelopes/headers or page-fetch timestamps. These cannot be recovered and
are not fabricated. New users extraction preserves each complete HTTP JSON body,
page timestamps, counts, hashes, and request/checkpoint scope. Users' actual capture
window is separate from the earlier notebook receipt cutoff; current plans cannot
be interpreted as historical plans or historical revenue loss.

The notebook cutoff is `2026-10-27T15:21:56.773109+00:00`. Full RAW retains the 19
later drive/warning receipts. Read-only validation applies the same cutoff and
checks notebook report counts, canonical sessions, warning joins, and weekly
numerators/denominators. Reproducibility uses files and fixed cutoffs, not CURRENT_DATE
or a silent API refresh. Immutable file checksums do not guarantee complete source
reporting or absence of concurrent historical backfills.

## Production evolution, outside this MVP

Move immutable page files/manifests to versioned encrypted S3, use a Snowflake
storage integration/external stage, and schedule extraction/loading on existing
AWS infrastructure. Retain the same snapshot IDs, provenance, watermark rules,
and reconciliation. Add concurrency control/monitoring as requirements justify.
No S3 infrastructure, AWS orchestration, CI/CD, production scheduling, dbt, or Steep
is implemented by this phase.

References: [API specification](https://qw7ytrkpd3swtndax6c4a73oua0mcrky.lambda-url.eu-west-1.on.aws/openapi.json),
[Python connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect),
[COPY](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table),
[load metadata limits](https://docs.snowflake.com/en/user-guide/data-load-considerations-load).

## Fresh pipeline command

`scripts/run_pipeline.py` assembles a new cumulative FULL_BASELINE from the last
fully successful pipeline parent and timestamp-filtered response pages. The first
run uses the approved validated snapshot. A local checkpoint advances only after
dbt build succeeds. Current users are fully refreshed. Parent and refreshed receipt
overlap uses maximum observed multiplicity of identical full payloads, without
session-level deduplication; original response pages remain archived. Distinct
receipt content remains distinct. `--full` fetches all source pages independently.
See `pipeline_run_guide.md` for exact commands, resume behavior, and limitations.
The default dbt vars and approved baseline remain unchanged.
