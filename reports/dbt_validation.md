# dbt validation — passed

Validated 28 October 2026 with dbt Core 1.12.6 / dbt-snowflake 1.12.4,
Python 3.12.11, and the dedicated OOONO_DBT role. dbt debug passed. The isolated
adapter uses connector 4.8.1; the Python 3.14 ingestion environment remains on
connector 5.1.0. Dependency resolution reports no broken requirements.

Snapshot: `e943b3aefc3411575c251ada7404c7013b54bf9510e8d37e9e69bd2f80bf863a`.
UTC receipt cutoff: `2026-10-27T15:21:56.773109+00:00`.
Both are configurable dbt vars with these fixed defaults; there is no latest-snapshot
lookup. Complete calendar weeks use the cutoff's Copenhagen reporting date and
provisional device wall-calendar start times. Known lower-edge partial coverage is
flagged at drive level and excluded from the weekly mart.

## Models

| Relation | Materialization | Rows | Grain |
| --- | --- | ---: | --- |
| STAGING.STG_DRIVES | view | 219,848 | Canonical session |
| STAGING.STG_WARNINGS | view | 315,601 | Canonical warning |
| STAGING.STG_USERS | view | 3,085 | User in current-state capture |
| STAGING.INT_DRIVE_CONNECTION_BEHAVIOR | table | 219,848 | Canonical session with aggregated warnings |
| ANALYTICS.MART_WEEKLY_RELEASE_HEALTH | table | 37 | Week × platform × app version |

Canonical sessions exactly match the notebook's 219,848. The three staging models
apply agreement checks before casting and preserve receipt lineage/anomaly flags.
The warning preaggregation prevents session fan-out. Current-state users are not
joined into historical plan/revenue claims.

## Exact weekly reconciliation

| Week starting | Platform | Eligible drives | Multi-connection drives | Share |
| --- | --- | ---: | ---: | ---: |
| 2026-10-12 | all | 21,711 | 1,519 | 7.00% |
| 2026-10-12 | android | 10,093 | 1,287 | 12.75% |
| 2026-10-12 | ios | 11,618 | 232 | 2.00% |
| 2026-10-19 | all | 21,595 | 1,422 | 6.58% |
| 2026-10-19 | android | 10,071 | 1,320 | 13.11% |
| 2026-10-19 | ios | 11,524 | 102 | 0.89% |

All numerators and denominators match the approved reference exactly. Overall
shares are weighted sums of counts, never averages of release/platform rates.
Distinct-driver counts are not additive across platform/version groups. The mart
uses 0–1 ratios; percentages here multiply by 100. Adjacent-week comparisons are
within the same platform/version and remain NULL when the preceding week is absent.

## Tests and known exceptions

Complete build: **5 models built, 26 data tests passed, 2 tests warned, 0 errors,
0 skipped**. dbt's total is PASS=31, WARN=2, ERROR=0 (passes include the 5 models).

- Canonical keys unique/nonnull; source identities and snapshot completion pass.
- Drive grain, foreign-key relationship, eligibility, warning totals, and replay
  reconciliation pass: 4,346 collapsed repeats and 315,449 matched warnings.
- Mart grain, numerator/denominator bounds/arithmetic, completeness filtering,
  WoW adjacency, and frozen overall/platform totals pass.
- `warning_clock_anomalies`: WARN 150. Rows remain in staging and are flagged in
  the drive aggregate; invalid interval clocks are excluded only from that warning
  measure's numerator, not silently deleted from source or staging.
- `warning_orphans`: WARN 152. These remain in stg_warnings and do not multiply or
  attach arbitrarily to drives. No warning user-ID mismatch was found.

No unexpected source/metric discrepancy was found. An initial dbt compilation
issue with its default test-audit schema was corrected by mapping test schemas
to STAGING; no metric definitions or receipt filters were changed to make totals
match. The known quality exceptions are deliberately nonfatal.

## RAW preservation and the 224,194 / 224,200 distinction

Final RAW checks still return 224,200 drives, 315,614 warnings, and 3,085 users for
the selected full snapshot. The six drive receipts and 13 warning receipts after
the notebook cutoff remain in RAW. Applying the cutoff BEFORE canonicalization
selects 224,194 drive reports and 315,601 warnings. No RAW source records were
changed, truncated, or business-deduplicated by dbt. The separate SMALL_TEST
snapshot is excluded by the explicit snapshot ID.

OOONO_DBT has SELECT-only grants on the four RAW tables. Its create permissions
are limited to STAGING/ANALYTICS; routine builds do not use ACCOUNTADMIN. Setup
administration is a separate command and ingestion retains OOONO_INGESTOR.

Local evidence: `data/dbt_validation/` contains per-phase run results and the final
read-only SQL reconciliation. dbt logs/target artifacts and all credentials are
ignored. See README for repeatable commands and docs/dbt_design.md for assumptions.
Connection count >1 is descriptive behavior, not a confirmed failed drive. The
existing iOS 6.3.0 instrumentation and device-time semantics caveats still apply.
No Steep implementation has been started.

## Project layout verification

The dbt project was moved into `dbt/`, with staging files grouped under
`models/staging/ooono/`. Python ingestion and reports remain repository-level.
The runner supplies the new project/profile directories explicitly. Post-move
`dbt parse`, `dbt debug`, and `dbt compile` passed and discovered the same five
models and 28 tests. Model SQL, metric definitions, baseline vars, and warehouse
relations are unchanged. The complete build results above remain the semantic
validation evidence; the layout check did not rebuild or modify RAW data.
