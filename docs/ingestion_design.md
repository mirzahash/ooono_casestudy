# Simple batch ingestion

```text
API pages → local landing files → temporary COPY tables → append-only RAW
                                                               ↓
                                                         dbt build/tests
                                                               ↓
                                                    mark run COMPLETE
```

A normal extraction starts at the last successful source-receipt cutoff stored in
Snowflake. First use fetches full history. Users have no receipt filter and are
replaced from a full current capture. Original response pages and extraction
checkpoints support local recovery; AWS deployment would move them to S3.

Drive/warning records are stored once using SHA-256 of canonical full payload plus
its occurrence number. This explicitly assumes content identity because a unique
drive-receipt ID is not documented. Different business values/receipt times remain
separate; repeated session IDs collapse later in staging. More identical copies
in a later extraction insert only the excess. This is not guaranteed exactly-once
physical event delivery. Concurrent loaders are not supported.

No cumulative snapshots, previous-history file merges, or automatic overlap. An
explicit --since or --full supports reconciliation. Incremental retrieval can miss
reports exposed later with older receipt timestamps. Full reconciliation also
cannot discover records already deleted by the API.

New RAW tables preserve payload, typed receipt timestamp, source ID, report hash,
first ingestion batch, source path and ingestion time. RAW events are append-only;
USER_PROFILES is replace-current. INGESTION_RUNS holds the successful watermark.
COPY validates before a transaction inserts unseen reports and the run registry
entry together. A successful load does not imply successful dbt publication.

Legacy snapshot tables are not used; old local snapshot files are archived outside
the project. The final mart schema and business definitions remain unchanged;
SNAPSHOT_ID is a compatibility label for the run.
See [run guide](pipeline_run_guide.md) and [validation](../reports/simplification_validation.md).
