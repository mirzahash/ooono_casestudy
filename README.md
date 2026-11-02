# OOONO weekly release health

A small batch pipeline for comparing recorded connection behavior across weeks,
platforms and app versions. Python retrieves reports, Snowflake stores them once,
and dbt builds tested drive-level and weekly models for Steep.

```text
Events API → local response pages → append-only Snowflake RAW
                                          ↓
                            dbt staging → drive-level table → weekly mart → Steep
```

## Run

New laptop: follow the [setup guide](docs/fresh_laptop_setup.md).
Once configured, run from the repository root:

```sh
.venv/bin/python scripts/run_pipeline.py
```

- First run: fetch all available records automatically.
- Subsequent runs: request drives/warnings since the last successful receipt cutoff.
- Users: fetch the full current list each run.
- Insert only unseen drive/warning reports into RAW. No cumulative history copies.
- Rebuild dbt models and run tests, then mark the warehouse run COMPLETE.

Recover a failed run using the directory printed when it started:

```sh
.venv/bin/python scripts/run_pipeline.py --run-dir data/landing/<existing-run-path>
```

Deliberately reconcile all source reports, inserting only unseen reports:

```sh
.venv/bin/python scripts/run_pipeline.py --full
```

See the [run guide](docs/pipeline_run_guide.md) for an explicit lookback and failures.
No notebook is required to operate the pipeline.

## How the code is organized

| File | Responsibility |
|---|---|
| `scripts/run_pipeline.py` | Extract → prepare files → load RAW → dbt → successful checkpoint |
| `scripts/api.py` | OAuth, pagination, bounded retries and extraction checkpoints |
| `scripts/ingest.py` | Stable report keys and compressed files for fetched records only |
| `scripts/snowflake_io.py` | Connection, bulk COPY/MERGE, current users, warehouse run history |
| `scripts/run_dbt.py` | Secure dbt wrapper; standalone builds use the last successful run |
| `scripts/setup_dbt.py` | One-time additive table and role setup |
| `scripts/check_snowflake.py` | Read-only diagnostics |
| `dbt/models/` | Staging views, one-row-per-drive table, weekly mart |
| `notebooks/` | Historical exploration and validation; not production entry points |

## Metrics and assumptions

- **Eligible drives:** canonical sessions with valid intervals, positive consistent
  durations and integer connection counts of at least one.
- **Multi-connection drives:** eligible sessions with `connection_count > 1`.
- **Multi-connection share:** SUM(multi-connection drives) / SUM(eligible drives).
  This is descriptive behavior, **not a confirmed failure rate**.
- Agreeing reports for a session collapse only after removing `received_at`.
  Conflicting business values trigger a blocking test; no arbitrary latest-wins rule.
- Device timestamps lack offsets, so weeks use provisional device wall-calendar
  dates. Receipt timestamps are UTC. Current and known partial first weeks are excluded.
- The API has no documented unique drive-report ID. Ingestion keys use the complete
  payload plus its occurrence number in the extraction. Identical repeats are not
  inserted again; different receipt times/business fields remain separate reports.
  This content-identity policy is an assumption, not proven physical event identity.
- No automatic lookback is applied. Recent receipts can describe old drives.
  Backdated API availability or revised records with old receipts may be missed;
  use deliberate lookback/full reconciliation. No polling window is claimed optimal.
- Users are current state, not historical subscription data. Source deletions do
  not delete stored event reports.

Definitions and findings: [metric contract](reports/metric_definitions.md),
[Product findings](reports/weekly_findings.md).

## Storage and cost choices

RAW uses `DRIVE_REPORTS`, `WARNING_REPORTS`, `USER_PROFILES` and `INGESTION_RUNS`.
Drive/warning history is stored once by report key; only current users are replaced.
Snowflake manages micro-partitions, with a typed receipt timestamp available for
filtering. Landing files are organized by extraction date, not claimed receipt date.
Local pages support recovery; there are no parent snapshots or manifests in the
operating path. Old snapshot files/tables are retained only for rollback/reference.

Staging remains views. Intermediate and mart remain full rebuilds at this dataset
size, which handles captured late reports without incremental update complexity.
This is not a claim that full dbt rebuilds are cheapest at arbitrary scale: measure
scans/runtime before adding affected-session merges or a rolling reporting window.
No monetary savings have been measured.

The mart name and 23-column schema are preserved for Steep. Its legacy
`SNAPSHOT_ID` column now labels the analytical run; it is not a cumulative dataset
ID. `ANALYSIS_RECEIPT_CUTOFF` still records the availability boundary. dbt reapplies
SELECT grants to `STEEP_READONLY` after rebuilding the mart.

## Tests and validation

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv-dbt/bin/python scripts/run_dbt.py debug
.venv-dbt/bin/python scripts/run_dbt.py build
```

Exact reference counts belong to the frozen interview baseline: 219,848 canonical
sessions and the weekly platform numerators/denominators recorded in the validation
report. New captures can revise historical results. Reference tests run only when explicitly requested with
`validate_baseline: true`; normal structural and consistency tests always run.
See [simplification validation](reports/simplification_validation.md) for the new
implementation's checks. Older validation reports describe the submitted snapshot
implementation and are retained as historical evidence.

## Intentional exclusions and OOONO deployment

No streaming, production scheduler, financial attribution, automated schema-drift
alerts, distributed locking, or historical user-plan reconstruction. RAW loading
is transactional; the complete dbt build is not an atomic publication, so failure
can leave partially updated derived models. One writer is assumed.

At OOONO, start with a scheduled AWS container running this batch pipeline,
S3 for durable landing files, Secrets Manager for credentials, and CloudWatch
for logs/alerts. Keep the successful cutoff in Snowflake. Streaming for Engineering
would require a separate latency/failure-signal discussion. This AWS deployment
is proposed, not implemented.

Credentials, private keys, local data/environments, generated dbt files and the
assignment PDF are excluded from Git. Never commit notebook record outputs.
