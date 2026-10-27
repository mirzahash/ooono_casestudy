# Provisional weekly connection behavior

Receipt cutoff: 2026-10-27T15:21:56.773109+00:00. Offline analysis; no source refresh.
Weeks use provisional device wall-calendar start dates. This is a comparison of
recorded connection behavior, not a confirmed assessment of failed drives.

## Data validation

| dataset | raw_rows | missing_id_rows | business_conflicting_ids | canonical_records | collapsed_replay_rows |
| --- | --- | --- | --- | --- | --- |
| drives | 224194 | 0 | 0 | 219848 | 4346 |
| warnings | 315601 | 0 | 0 | 315601 | 0 |

Repeated drive reports agree on every observed business field; collapse receipt-only
replays to one session, retaining earliest/latest observed receipt and report count.
Warnings match canonical drives at 99.952%; 152
remain unmatched, with no user-ID mismatches among comparable matches.
There are 150 future warning-clock flags and
150 matched warnings outside the drive interval.

## Last two complete calendar weeks

| week | eligible_drives | drivers | drives_with_multiple_connections | median_duration_s | p95_connections | multiple_connection_pct | drivers_with_multiple_connection_drives |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-12 | 21711 | 2462 | 1519 | 1000.0 | 2.0 | 6.996 | 804 |
| 2026-10-19 | 21595 | 2472 | 1422 | 990.0 | 2.0 | 6.585 | 725 |

The multiple-connection share changed by -0.411 percentage points.
Distinct-driver counts measure drivers with this recorded behavior, not drivers
proven to have had a failed drive. Driver totals are not additive across versions.

## Platform and release context

| week | platform | eligible_drives | drivers | drives_with_multiple_connections | median_duration_s | p95_connections | multiple_connection_pct | drivers_with_multiple_connection_drives |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-12 | android | 10093 | 1126 | 1287 | 994.0 | 3.0 | 12.751 | 650 |
| 2026-10-12 | ios | 11618 | 1337 | 232 | 1004.0 | 1.0 | 1.997 | 154 |
| 2026-10-19 | android | 10071 | 1124 | 1320 | 987.0 | 3.0 | 13.107 | 671 |
| 2026-10-19 | ios | 11524 | 1349 | 102 | 992.5 | 1.0 | 0.885 | 54 |

| week | platform | app_version | eligible_drives | drivers | drives_with_multiple_connections | median_duration_s | p95_connections | multiple_connection_pct | drivers_with_multiple_connection_drives |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-12 | android | 6.1.0 | 271 | 27 | 22 | 999.0 | 2.5 | 8.118 | 15 |
| 2026-10-12 | android | 6.2.0 | 9822 | 1108 | 1265 | 994.0 | 3.0 | 12.879 | 636 |
| 2026-10-12 | ios | 6.1.0 | 107 | 1 | 0 | 854.0 | 1.0 | 0.0 | 0 |
| 2026-10-12 | ios | 6.1.1 | 2344 | 380 | 232 | 1016.0 | 3.0 | 9.898 | 154 |
| 2026-10-12 | ios | 6.3.0 | 9167 | 1158 | 0 | 1001.0 | 1.0 | 0.0 | 0 |
| 2026-10-19 | android | 6.1.0 | 112 | 10 | 3 | 972.5 | 1.0 | 2.679 | 3 |
| 2026-10-19 | android | 6.2.0 | 9959 | 1119 | 1317 | 987.0 | 3.0 | 13.224 | 668 |
| 2026-10-19 | ios | 6.1.0 | 103 | 1 | 0 | 1056.0 | 1.0 | 0.0 | 0 |
| 2026-10-19 | ios | 6.1.1 | 772 | 117 | 102 | 952.0 | 3.0 | 13.212 | 54 |
| 2026-10-19 | ios | 6.3.0 | 10649 | 1289 | 0 | 996.0 | 1.0 | 0.0 | 0 |

The observed iOS 6.3.0 cohorts have no multiple-connection drives in these weeks.
That warrants checking counter semantics and instrumentation; it does not prove
zero interruptions. Adoption changes can alter aggregate rates even without
within-version improvement. Release comparisons are observational and confounded
by platform, duration, device, rollout population, and instrumentation.

## Timing and limitations

Most device end clocks are about two hours ahead of UTC receipt clocks in continental
countries and one hour ahead in GB, consistent with local clocks plus arrival delay.
This is evidence, not a timezone contract; country alone is insufficient. Do not
interpret negative clock differences as negative latency. See notebook duration/device
strata and +/-2-hour boundary sensitivity checks.

The saved cutoff includes reports arriving after their calendar week closed.
Further late reports can revise the results. Full pagination is not proof that all
attempted drives were reported, and the incremental refresh cannot guarantee older
backdated receipts. Confirm source timestamp and connection-count meanings before
using the candidate metric as a product-health KPI. Warning frequency and missing
actions do not establish missed alerts. No causal or monetary claim is supported.

Metric contract: [metric_definitions.md](metric_definitions.md).
