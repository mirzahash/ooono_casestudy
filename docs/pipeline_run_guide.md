# Run the batch pipeline

Run from the repository root after the [fresh-laptop setup](fresh_laptop_setup.md).

```sh
.venv/bin/python scripts/run_pipeline.py
```

1. Read the last COMPLETE cutoff from RAW.INGESTION_RUNS.
2. Fetch drive/warning reports received since that cutoff; fetch users in full.
   With no previous success, automatically fetch all records. No 24-hour overlap.
3. Save original API pages and cursor checkpoints locally.
4. Prepare load files for these fetched records only. Never reread parent history.
5. COPY into temporary tables, MERGE unseen report keys into RAW, and replace
   current users. Commit these changes and a RAW_LOADED run record together.
6. Build/test dbt with this run ID and cutoff explicitly supplied.
7. On success, mark the warehouse run COMPLETE. New runs use its cutoff.

## Resume

The command prints a folder under `data/landing/extraction_date=YYYY-MM-DD/<id>`.
Reuse its exact path:

```sh
.venv/bin/python scripts/run_pipeline.py --run-dir data/landing/<existing-run-path>
```

Saved `run.json` retains request scope and cutoff. Page checksums are verified;
completed extraction is reused. Already committed batches are not reinserted.
Resume with --run-dir only, including for runs originally started with --full.
A newer successful run prevents replaying an older run over current users/models.

API cursor expiry requires a new run. dbt failure leaves the successful cutoff
unchanged; RAW may already be committed and some models rebuilt. Resolve/resume
before presenting results; there is no atomic warehouse-wide model publication.

## Full reconciliation or deliberate lookback

```sh
.venv/bin/python scripts/run_pipeline.py --full
.venv/bin/python scripts/run_pipeline.py --since 2026-10-27T00:00:00+00:00
```

These refetch reports, but stable keys prevent repeated history inserts. Choose
lookback based on source behavior; no duration is claimed empirically optimal.
The receipt filter cannot guarantee capture of backdated API availability.

## dbt separately

```sh
.venv-dbt/bin/python scripts/run_dbt.py debug
.venv-dbt/bin/python scripts/run_dbt.py build
```

Standalone build/run/test uses the last successful warehouse run ID and cutoff.
The pipeline supplies its candidate cutoff before advancing that checkpoint.
There is no hardcoded original snapshot fallback. Explicit --vars can be used for
controlled validation, but receipt cutoff alone cannot reconstruct historical users
or exactly reproduce RAW as it existed before backdated reports were ingested.

## Files and logs

- `data/landing/.../<endpoint>/page_*.json`: original API responses.
- Endpoint `checkpoint.json`: next cursor, saved page counts and checksums.
- Run `run.json`: this attempt's cutoff, ID and progress.
- Run `load_result.json`: load status and inserted counts.
- Run `dbt_target/run_results.json`: this invocation's model/test results.
- `dbt/logs/dbt.log`: dbt diagnostic log.
- RAW.INGESTION_RUNS: shared successful cutoff and load/completion status.

There are no newly generated cumulative snapshots, parent manifests, or local
pipeline_state.json checkpoints. Obsolete local work is archived outside the project.
