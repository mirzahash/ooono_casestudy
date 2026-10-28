# RAW ingestion validation

Status: PASSED. No dbt or Steep models have been created.

Full snapshot ID: `e943b3aefc3411575c251ada7404c7013b54bf9510e8d37e9e69bd2f80bf863a`.
Notebook receipt cutoff: `2026-10-27T15:21:56.773109+00:00`.
Validation time: `2026-10-27T22:03:48.940196+00:00`.
Users capture: `2026-10-27T22:00:04.680570+00:00` to
`2026-10-27T22:00:22.238480+00:00`; current-state users are not an
as-of reconstruction of the earlier notebook cutoff.

| Endpoint | Manifest rows | Snowflake RAW rows | Result |
| --- | ---: | ---: | --- |
| Drives | 224,200 | 224,200 | Match |
| Warnings | 315,614 | 315,614 | Match |
| Users | 3,085 | 3,085 | Match |

The source arrays, file SHA-256 values, every prepared payload/hash/ordinal and
source metadata were validated locally. COPY landing rows were reconciled to RAW
for every payload, hash, receipt, ID, ordinal, file name, and file checksum before
commit. No missing IDs or invalid receipts were found; users have no source receipt
field and retain SQL NULL there. No RAW data was truncated or replaced.

## Notebook reconciliation

| Check | Notebook | Snowflake | Result |
| --- | ---: | ---: | --- |
| Drive reports by cutoff | 224,194 | 224,194 | Match |
| Canonical sessions | 219,848 | 219,848 | Match |
| Preserved extra receipt reports | 4,346 | 4,346 | Match |
| Business-field conflicting session IDs | 0 | 0 | Match |
| Warnings by cutoff | 315,601 | 315,601 | Match |
| Matched warnings | 315,449 | 315,449 | Match |
| Drive metric eligibility exclusions | 0 | 0 | Match |
| 12 October week: eligible drives | 21,711 | 21,711 | Match |
| 12 October week: multi-connection drives | 1,519 | 1,519 | Match |
| 19 October week: eligible drives | 21,595 | 21,595 | Match |
| 19 October week: multi-connection drives | 1,422 | 1,422 | Match |

Canonicalization here is a read-only reconciliation CTE, not ingestion deduplication
or a materialized dbt model. RAW retains repeated reports and all 19 receipts after
the cutoff. Connection counts are descriptive, not proof of failed drives.

## Idempotency test

A separate SMALL_TEST snapshot loaded five rows per endpoint, including repeated
session IDs with different source receipts. Loading the identical snapshot again
returned ALREADY_LOADED and kept all three counts at five. The test snapshot remains
separate in RAW; do not include it in FULL_BASELINE reporting totals. Tests preserve
rather than erase data to demonstrate rerun safety.

Five focused automated tests passed: cursor continuation despite short pages,
completed checkpoint reuse/corruption checks, request-scope and repeated-cursor
rejection, page-guard incompleteness, and preserved receipt ordinals/source integrity.

## Remaining limitations

Only snapshot-level idempotency is implemented. Identical records can recur in
other snapshots; lineage/hash comparisons support future overlap handling. There
is no independent documented drive-receipt ID. The source is live, late/backdated
records may be absent, device timezone semantics remain provisional, and the users
capture is later than the baseline. See [ingestion design](../docs/ingestion_design.md).
