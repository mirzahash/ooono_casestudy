# Run ingestion through dbt

Run commands from the repository root. The existing `.env`, encrypted key pair,
OOONO_INGESTOR / OOONO_DBT roles, both Python environments, and validated baseline
must already be configured. No role setup or key registration is needed each run.

## Normal fresh-data run

```sh
.venv/bin/python scripts/run_pipeline.py
```

This command:

1. Reads the last fully successful local pipeline checkpoint, or starts from the
   approved frozen baseline on the first run. It does not select the latest RAW
   snapshot automatically.
2. Freezes an analysis receipt cutoff at run start.
3. Fetches drives/warnings received since the parent's successful cutoff minus
   24 hours. Users are fully fetched because they have no receipt filter.
4. Preserves complete response JSON bodies, page checksums/timestamps, and cursors
   in ignored local run files. It verifies parent bytes and completes pagination.
5. Builds a new immutable, cumulative FULL_BASELINE snapshot from historical parent
   records plus refreshed observations and current users. The parent is unchanged.
6. Verifies every source file, payload, ordinal, metadata value, and checksum; then
   bulk-loads the new snapshot append-only to RAW with snapshot-level idempotency.
7. Runs dbt build with the new snapshot_id and receipt_cutoff explicitly supplied
   as vars. Project defaults remain pinned to the original validated baseline.
8. Advances `data/pipeline_state.json` only when extraction, RAW load, and all
   blocking dbt tests succeed. Known warning-level quality exceptions remain visible.

The command prints its run directory, endpoint counts, snapshot ID, dbt results,
and final COMPLETE summary. It does not push Git changes or start Steep.

## Resume a failed or interrupted run

Choose a readable name up front if convenient:

```sh
.venv/bin/python scripts/run_pipeline.py --run-dir data/pipeline_runs/interview_demo
```

Repeat the exact same command to resume that run. Saved pages are verified and
reused, a frozen snapshot is reused, and previously loaded RAW keys are not inserted
again. dbt builds/tests again. Reusing a completed directory replays the same
snapshot; omit --run-dir or choose a new directory for genuinely fresh data.
A local lock permits only one pipeline process at a time.

If a run fails, the successful checkpoint remains unchanged. RAW may contain its
successfully committed snapshot, and dbt may have rebuilt only some derived models.
Resume the failed run to finish, or restore the validated baseline with the fallback
command below. Do not assume a failed build leaves every derived model unchanged.
An invalid source cursor requires a separate new run; do not splice a restarted
scan into an old checkpoint.

## Full source refresh

```sh
.venv/bin/python scripts/run_pipeline.py --full
```

This reads all pages of all three endpoints, without timestamp filters or a parent
merge. It takes longer and is useful for historical reconciliation. Resume an
interrupted full run with both --full and the same --run-dir. No scheduling or
production orchestration is implemented.

## Overlap and receipt identity

The refreshed snapshot remains a full cumulative dataset so existing dbt models
can select exactly one ID. It is not just a delta pretending to be full history.
RAW retains the old and new snapshots; never sum rows across snapshots for analysis.

During snapshot assembly, identical full payloads in the overlap are combined with
maximum observed multiplicity: if the parent saw two identical records and the
fresh query sees three, retain three, not five. Different receipt timestamps or
any other payload differences remain separate records. This is not session-level
business deduplication. All original refreshed response pages remain archived.

The API has no independently documented drive-receipt ID. Identical content cannot
prove physical delivery identity; the overlap multiplicity rule is an explicit MVP
assumption. A 24-hour lookback can miss older backdated receipts, and incremental
runs do not detect source deletions. Use periodic --full reconciliation if required.
The live API has no documented transactional snapshot guarantee. Users capture
occurs during the run, not necessarily at the drive/warning receipt cutoff.

## Reproduce the original interview baseline

```sh
.venv-dbt/bin/python scripts/run_dbt.py build
```

This selects the checked-in approved snapshot/cutoff defaults and restores the
validated baseline models. It does not call the API or advance pipeline state.
Original notebook reference totals apply only to those defaults. Fresh snapshots
run structural, quality, and metric consistency tests, not the old exact counts.
New totals must be inspected rather than forced to match a historical reference.

Run evidence is in `data/pipeline_runs/<run>/run.json`, `load_result.json`, and
`dbt_run_results.json`; immutable source/load files are under `data/snapshots/`.
All are ignored in Git. Do not publish raw response pages, tokens, credentials,
private keys, or local logs.
