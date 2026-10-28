# OOONO release-health exploration

Work in progress for an Analytics Engineer interview case. The notebooks inspect
the Events API and profile release-related activity. Snapshot-first Python ingestion and five dbt models are implemented and validated.
There is no confirmed drive-failure metric or implemented Steep dashboard.

## Run locally

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your own API credentials to `.env`. Open the notebooks from the project root
in VS Code with Jupyter support and select `.venv/bin/python` as the kernel.
Run cells from top to bottom.

| Notebook | Purpose |
| --- | --- |
| `01_api_exploration.ipynb` | Fetch five sample records from drives, warnings, and users; inspect columns. |
| `02_data_profiling.ipynb` | Fetch and cache all historical drives and warnings; inspect identity, nulls, distributions, timestamps, and joins. |
| `03_event_counts.ipynb` | Independently count all API rows and distinct IDs without retaining full payloads. |
| `04_weekly_connection_behavior.ipynb` | Use cached records offline to validate canonical IDs, examine timestamps, and compare provisional weekly connection behavior. |

Profiling and counting cache their progress under `data/`. Completed reruns use
saved data without API calls; interrupted downloads resume. A new cache requires
fresh API pagination. The counting notebook performs its own scan, so it is not
needed to run profiling. The API is live and can change during pagination.
The fourth notebook exports aggregate results to `reports/weekly_findings.md`;
its proposed metric is documented in `reports/metric_definitions.md`. It uses
device wall-calendar week labels provisionally; source timezone semantics and
connection-counter meaning remain unconfirmed.
Notebook 04 currently points to the frozen local
`data/analysis_snapshot_20261027/` reconstructed from a completed backup and refresh;
the active profiling cache was later found incomplete. Local data is not shipped
with the repository. For a new analysis, finish notebook 02 and explicitly point
notebook 04's `CACHE` at that complete extract; results will reflect its cutoff.
The ingestion architecture in `docs/ingestion_design.md` is approved. Connection
helpers and RAW loading are implemented and validated. See `reports/raw_validation.md`.

## Snowflake connection — implementation step 1

Copy the Snowflake setting names from `.env.example` into local `.env` and supply
the account identifier, username, role, warehouse, database, schema, and supported
authentication method. Preserve the existing API settings. For encrypted key-pair
authentication, keep the private key outside Git. For normal password/MFA login,
use `SNOWFLAKE_AUTHENTICATOR=username_password_mfa`; the password is prompted and
not stored. `externalbrowser` requires configured browser SSO.

```sh
python scripts/check_snowflake.py --check-config
python scripts/check_snowflake.py
```

The first command checks local settings; the second checks live identity, existing
objects, usage, and direct role grants without creating or loading tables. Read
access does not by itself prove future write permissions. RAW ingestion and dbt are complete; Steep remains unimplemented.
The profiling notebook's latest local cache was refreshed on 27 October 2026
using a 24-hour overlap on receipt time; that one-off refresh is not an automated
notebook feature. Backdated receipts outside the overlap may be missed.

## Assumptions and limitations

- Receipt timestamps are UTC; device timestamps without offsets need semantic
  validation before weekly reporting.
- Multiple recorded connections are descriptive behavior, not confirmed failures.
- Repeated drive reports need a business-identity policy; profiling currently
  excludes repeated IDs conservatively from joins.
- Missing warning actions do not establish ignored warnings or product failure.
- The primary weekly metrics and release comparisons remain proposals.
- Streaming, financial attribution, production orchestration, and cloud deployment
  are deliberately outside the current exploration.

The intended production mapping is Python ingestion on AWS, raw data in Snowflake,
dbt transformations, and reporting in Steep. See `PROJECT_CONTEXT.md` for project
context and planned work. Snowflake RAW ingestion is implemented; AWS deployment,
and Steep reporting are still future work; dbt is implemented.

## Repository hygiene

Credentials, raw data, local environments, the supplied interview PDF, and local
dbt profiles are excluded. Notebook outputs are cleared before committing to avoid
publishing sample records. Do not commit outputs after running the notebooks.

## Frozen snapshot ingestion

Use an authorized setup role for the one-time additive SQL setup. Normal loads use
OOONO_INGESTOR, configured locally after the existing account was verified.

```sh
# One time, after verifying the existing warehouse/database/schema:
SNOWFLAKE_ROLE=ACCOUNTADMIN python scripts/ingest.py setup
# Preserve a small test snapshot and complete users response pages:
python scripts/ingest.py prepare --sample
# Substitute the printed snapshot directory; run twice to verify no extra rows:
python scripts/ingest.py load data/snapshots/<test_snapshot_id>
python scripts/ingest.py load data/snapshots/<test_snapshot_id>
# Freeze the validated drive/warning baseline and reuse the users capture:
python scripts/ingest.py prepare
python scripts/ingest.py verify data/snapshots/<full_snapshot_id>
python scripts/ingest.py load data/snapshots/<full_snapshot_id>
python scripts/ingest.py validate data/snapshots/<full_snapshot_id>
python -m unittest discover -s tests -v
```

`prepare` defaults to the local `data/analysis_snapshot_20261027/` baseline. That
baseline is intentionally not distributed. A new environment must first obtain a
complete approved baseline and manifest; do not treat the notebook's mutable or
incomplete cache as equivalent. Users capture is later/current state, not historical
plan data. `prepare` reuses its completed `data/ingestion_work/users_extraction/`
checkpoint without another API call; a fresh users capture requires a new `--work`
directory. No drives/warnings API extraction is performed by this import command.

The `validate` command targets the approved 27 October baseline reference totals;
new analytical baselines require new reference totals, not silently reused checks.
`verify` and snapshot loading are generic for the manifest format. Tests using the
local small snapshot skip when that ignored fixture is absent; the pagination
invariant tests run without credentials or the API.

The validated FULL_BASELINE ID is
`e943b3aefc3411575c251ada7404c7013b54bf9510e8d37e9e69bd2f80bf863a`.
It contains 224,200 drives, 315,614 warnings, and 3,085 users. Query RAW with the
chosen snapshot ID or join the manifest and filter its purpose. The separate
SMALL_TEST snapshot remains in RAW; summing all snapshots double-counts records.

Rerunning the same snapshot is idempotent on `(snapshot_id, source_ordinal)`.
Different snapshots may overlap. No source reports are business-deduplicated at
load time. File/record checksums, original payloads, source receipts, ordinals, and
load timestamps are retained. This is an initial-load MVP: timestamp-filtered API
helpers exist, but no automatic incremental watermark framework is implemented.
The future daily-overlap strategy and source identity limitations are documented
in `docs/ingestion_design.md`. RAW validation passed and dbt is implemented. Steep has not been started.

## dbt Core — validated frozen baseline

Separate guide: [dbt installation and setup](docs/dbt_installation_guide.md).

The isolated environment keeps the ingestion connector and dependencies intact:

```sh
python3.12 -m venv .venv-dbt
.venv-dbt/bin/python -m pip install -r requirements-dbt.txt
# One-time administrator grants only, after reviewing sql/dbt_setup.sql:
.venv/bin/python scripts/setup_dbt.py
.venv-dbt/bin/python scripts/run_dbt.py debug
.venv-dbt/bin/python scripts/run_dbt.py build
```

`run_dbt.py` loads local `.env`, uses OOONO_DBT, and generates ignored `dbt/profiles.yml`
from `dbt/profiles.yml.example` if absent. It never changes SNOWFLAKE_ROLE used
by ingestion. The encrypted key passphrase is passed through dbt's secret environment
variable handling. No ACCOUNTADMIN is used for dbt debug/build. Existing STAGING
and ANALYTICS schemas contain the derived models; RAW is read-only to this role.

Defaults in `dbt/dbt_project.yml` select the approved full snapshot and notebook cutoff.
Override deliberately with dbt vars, never by switching to latest implicitly:

```sh
.venv-dbt/bin/python scripts/run_dbt.py build --vars '{"snapshot_id":"<full_snapshot_sha256>","receipt_cutoff":"<ISO_8601_UTC_timestamp>"}'
```

Changing vars changes the analytical baseline; it does not extract or load new
records. Notebook-reference count tests apply only to the exact default ID/cutoff;
other baselines still run structural/quality tests but require their own reference
reconciliation. All snapshots must be completed FULL_BASELINE captures.

Staging views type payloads and collapse only agreeing business records after the
receipt cutoff. They retain anomaly flags and receipt lineage. The drive-level
STAGING table aggregates warnings before joining. The ANALYTICS weekly table has
one row per week/platform/version, exact numerator/denominator counts, 0–1 shares,
distinct drivers, descriptive multi-connection-driver counts, duration context,
and adjacent-week changes. Current and known partial first calendar weeks are
excluded. Driver counts are not additive across groups; overall rates require
SUM(numerator)/SUM(denominator), never the average of rates.

The build has 28 data tests: 26 pass and two intentionally warn for 150 anomalous
warning clocks and 152 orphan warnings. Both remain in staging, not silently deleted.
See `reports/dbt_validation.md` for exact overall and platform reconciliation.
In dbt logs a successful build shows 31 passes (5 models + 26 tests), 2 warnings,
and 0 errors. No Steep work has been started.
