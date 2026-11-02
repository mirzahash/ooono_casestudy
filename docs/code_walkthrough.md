# Interview code walkthrough

Start with the business question and the metric definitions. Then show this flow:

```text
run_pipeline.py
  1. Read the last successful receipt cutoff from Snowflake.
  2. api.py fetches reports and saves pages/progress locally.
  3. ingest.py gives each fetched report a stable key and prepares load files.
  4. snowflake_io.py inserts only previously unseen reports into RAW.
  5. run_dbt.py builds models and runs tests.
  6. Mark the run successful so the next request can start at its cutoff.
```

## What to say at each file

- **run_pipeline.py:** “This coordinates the batch. First run fetches everything;
  later runs start at the successful receipt cutoff. Failed runs can resume using
  their saved directory, and a failed dbt build does not advance the cutoff.”
- **api.py:** “Follow the cursor until no next page remains. Retry transient errors
  with a bounded delay. Save original pages and verify them when resuming.”
- **ingest.py:** “Prepare only fetched reports, not a copy of history. The API lacks
  a documented unique drive-report ID, so full payload plus occurrence number is
  our explicit identity assumption. Different receipt times remain separate.”
- **snowflake_io.py:** “Bulk-load to temporary tables, validate, then MERGE missing
  report keys. Repeated retrieval does not repeat RAW inserts. Users are replaced
  from the full current list. A transaction protects RAW and its run record.”
- **dbt staging:** “Extract/type fields, preserve quality flags and collapse only
  agreeing reports. A conflict triggers a test instead of arbitrary latest-wins.”
- **Intermediate:** “Count warnings before joining, preserving one row per drive.”
- **Mart:** “Group eligible drives by complete week, platform and version. Use
  summed numerators/denominators for overall share; this is not a failure rate.”

## Decisions and limits

- Batch/local disk fit the laptop MVP; production would use durable landing storage
  and a scheduler. No streaming or AWS deployment is claimed.
- There is no automatic 24-hour lookback: saved comparisons did not establish its
  necessity. Backdated availability remains a risk; --since/--full reconcile it.
- RAW reports are stored once. We removed cumulative snapshot copying. Old snapshot
  tables/files are kept only to verify results and permit rollback.
- Full dbt rebuilds are simple at this size, but cost/runtime need measurement before
  claiming production scalability. Incremental intermediate logic remains deferred.
- The RAW transaction does not make the whole dbt build atomic. Concurrent distributed
  writers, schema alerts and source deletion propagation are not implemented.
- The final mart retains its 23 columns for Steep. SNAPSHOT_ID now means the run ID;
  the name is kept for compatibility, not because datasets are being copied.

See reports/simplification_validation.md for checks actually performed. Avoid
claiming that an implementation parameter is supported by data unless tested.
