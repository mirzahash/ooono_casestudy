# Simplified pipeline validation

Validated on 2 November 2026 on `feature/simplify-batch-ingestion`.

## What changed

API reports now flow into append-only RAW without cumulative snapshots. The first
run fetches all data; normal runs use the last COMPLETE warehouse receipt cutoff.
Only newly observed full-payload/occurrence keys are inserted. Users are a full
replace-current capture. No automatic 24-hour lookback, parent manifests, snapshot
merge or hardcoded baseline is in the runtime path.

New tables: RAW.DRIVE_REPORTS, WARNING_REPORTS, USER_PROFILES, INGESTION_RUNS.
Legacy DRIVES/WARNINGS/USERS/INGESTION_SNAPSHOTS are not used by the new dbt
sources. They were left intact during migration; obsolete local snapshot files
were subsequently archived outside the project.

## Frozen-baseline reconciliation

Seeded the new tables once from checksum-verified baseline source files and ran
dbt with its original cutoff and validate_baseline=true. This was a controlled
migration/validation, not the normal extraction path.

| Check | Result |
|---|---:|
| RAW drive reports | 224,200 |
| RAW warning reports | 315,614 |
| Current users | 3,085 |
| Canonical sessions | 219,848 |
| Week 12 October eligible / multi | 21,711 / 1,519 |
| Week 19 October eligible / multi | 21,595 / 1,422 |
| Android 12 October eligible / multi | 10,093 / 1,287 |
| Android 19 October eligible / multi | 10,071 / 1,320 |
| iOS 12 October eligible / multi | 11,618 / 232 |
| iOS 19 October eligible / multi | 11,524 / 102 |

All three fixed-reference dbt checks passed. Full build: five models, 26 passing
tests, two expected warning tests (150 warning-clock anomalies, 152 orphans).

## Compatibility with the pre-change latest dataset

Imported the latest saved capture once. Of its 236,240 drive and 332,106 warning
reports, only 12,040 drives and 16,492 warnings were new relative to the baseline
already loaded. Rebuilt at its original cutoff.

Compared the resulting mart against a saved pre-change query:

- All **23 columns**, order, data types, numeric precision/scale and VARCHAR widths
  match exactly. An initial VARCHAR-width difference was corrected before final validation.
- All **37 rows** match, with floating values compared at 1e-12 tolerance.
- Legacy RAW drive count is unchanged.
- STEEP_READONLY retains SELECT on the rebuilt mart.

The legacy SNAPSHOT_ID column now labels the analytical run. Its name and type
are preserved for consumers, but there is no longer a copied dataset per ID.

## Real API-to-dbt update

Executed the new run_pipeline.py against the live API:

| Endpoint | Fetched | Inserted into RAW |
|---|---:|---:|
| Drives | 8,412 | 8,411 |
| Warnings | 11,521 | 11,520 |
| Users | 3,154 | 3,154 replace-current rows |

The boundary reports already represented in RAW were skipped. dbt built five
models and passed 26 tests; two warning tests exposed 168 warning-clock anomalies
and 32 orphan warnings. Zero errors/skips. Successful warehouse checkpoint advanced
only after build/test success.

Current totals after this update: **244,651 drive reports, 343,626 warning reports,
3,154 current users, and 239,887 canonical sessions**. These are fresh-data totals,
not a claim that new data equals the historical baseline. The live mart now uses
this newer cutoff and includes newly complete reporting weeks.

## Different-batch replay

Replayed the same fetched reports under a different batch ID. Result:

- **0 drive reports inserted.**
- **0 warning reports inserted.**
- Users replaced by the same 3,154 profiles.
- No duplicate report keys; successful checkpoint unchanged.

This demonstrates report-level idempotency across batches, not just skipping a
repeated snapshot ID. The probe remains RAW_LOADED, not a falsely certified dbt
success. No claim of distributed exactly-once processing is made.

## Other checks and remaining limits

- 13 offline tests pass: pagination/resume/checksums, stable report identity,
  multiplicity/changed payload preservation, batch validation, transaction rollback,
  failed-build recovery and dbt variable selection.
- dbt debug passes with OOONO_DBT; all Python scripts parse and whitespace checks pass.
- No new dependencies or credentials were introduced.
- Stable content keys remain an assumption without a documented unique receipt ID.
  Concurrent distributed writers, API source snapshot isolation, source deletions,
  backdated availability guarantees and atomic dbt publication are not implemented.
- Full dbt rebuilds remain. Reduced RAW inserts are demonstrated; Snowflake monetary
  savings and production-scale scan/runtime reductions have not been measured.
- Exact historical replay is not guaranteed by receipt cutoff alone after future
  backdated ingestion or changes to current users. Original local snapshots are archived
  outside the project.

Local detailed evidence is ignored under data/simplification_validation/ and
data/landing/simplified_live_demo/. No individual source records are published here.

## 3 November: default-folder upload fix

A normal run exposed Snowflake error 253006: Path.as_uri() encoded '=' in
extraction_date=YYYY-MM-DD as '%3D', which the upload connector treated literally.
PUT now receives the quoted, unencoded local file path. A regression test covers
both '=' and spaces. Future CLI failures include errno/sqlstate/query ID when
available, without printing connector messages that may contain sensitive details.

Resumed the failed run using its existing pages (no new API extraction). RAW
loading and all five dbt models completed, with 26 passing tests and two expected
warning tests (172 warning-clock anomalies and eight orphans). The run reached
COMPLETE. All 14 offline tests pass. The earlier custom demo directory lacked '='
and therefore had not exercised this path case.
