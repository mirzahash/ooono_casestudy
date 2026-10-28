# Weekly Product findings

As of 2026-10-27T15:21:56.773109+00:00; cached snapshot, no new API requests.
Comparison: 2026-10-12–2026-10-18
versus 2026-10-19–2026-10-25.
Weeks are provisional device wall-calendar weeks, not a confirmed timezone conversion.

## 1. The aggregate connection signal improves, but cannot establish better drive experience

The share of eligible reported drives with multiple connections changed from
6.996% to
6.585% (-0.411 percentage points).
Android moved from 12.751% to
13.107%; iOS from
1.997% to
0.885%.
Changing iOS version adoption can affect the aggregate. This is recorded connection
behavior, not a failed-drive rate or evidence of a release causing improvement.

| week | eligible_drives | drives_with_multiple_connections | multiple_connection_pct | drivers_with_multiple_connection_drives |
| --- | --- | --- | --- | --- |
| 2026-10-12 | 21711 | 1519 | 6.996 | 804 |
| 2026-10-19 | 21595 | 1422 | 6.585 | 725 |

## 2. iOS 6.3.0 raises a counter/instrumentation question across device categories

Across all available eligible history, iOS 6.3.0 has 26,367 drives,
0 with multiple connections, and a connection
range of 1–1.
The version/device table tests whether this persists for each observed category.
`device` describes CO-DRIVER categories, not iPhone models. Some earlier-version
cohorts have few drivers; history-wide comparisons also have different date coverage.
Check counter semantics or release instrumentation before treating its zero rate
as evidence of stability. These observations do not prove an instrumentation defect.

| app_version | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- |
| 6.1.0 | 22223 | 1238 | 616 | 600 | 126 |
| 6.1.1 | 59585 | 3325 | 1678 | 1711 | 374 |
| 6.3.0 | 26367 | 0 | 0 | 0 | 0 |

| app_version | device | drives | multiple_connection_drives | connection_min | connection_max |
| --- | --- | --- | --- | --- | --- |
| 6.1.0 | CD1 | 7390 | 802 | 1 | 5 |
| 6.1.0 | CD2 | 10915 | 1261 | 1 | 5 |
| 6.1.0 | CD3 | 3422 | 341 | 1 | 5 |
| 6.1.0 | none | 2115 | 176 | 1 | 4 |
| 6.1.0 | unknown | 961 | 0 | 1 | 1 |
| 6.1.1 | CD1 | 20539 | 2201 | 1 | 5 |
| 6.1.1 | CD2 | 30031 | 3438 | 1 | 5 |
| 6.1.1 | CD3 | 10007 | 966 | 1 | 5 |
| 6.1.1 | none | 6096 | 483 | 1 | 4 |
| 6.3.0 | CD1 | 8228 | 0 | 1 | 1 |
| 6.3.0 | CD2 | 11348 | 0 | 1 | 1 |
| 6.3.0 | CD3 | 4189 | 0 | 1 | 1 |
| 6.3.0 | none | 2602 | 0 | 1 | 1 |

## 3. Duration and warning activity provide context, not proof of missed alerts

For 6.3.0 across available history, median duration is 1002 seconds,
p95 is 3300.8 seconds, and observed matched warnings average
1.448 per drive. Compare versions in the same weeks
below; warning rates depend on exposure, routes, warning types, and driver mix.
In the latest complete week, 6.3.0 and 6.1.1 have similar interval-valid warning activity (4.061 versus 4.013 per drive-hour), with median durations 996 versus 952 seconds. There is no clear warning-activity collapse in this comparison. Neither a lower warning rate nor a zero-warning drive proves an alert was missed.
There is no expected-warning denominator or explicit drive-failure outcome.

| week | app_version | drives | drivers | multiple_connection_pct | duration_p50_s | duration_p95_s | matched_warnings_per_drive | valid_warnings_per_drive_hour | zero_observed_warning_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-12 | 6.1.0 | 107 | 1 | 0.0 | 854.0 | 2772.0 | 0.0 | 0.0 | 100.0 |
| 2026-10-12 | 6.1.1 | 2344 | 380 | 9.898 | 1016.0 | 3393.4 | 1.488 | 4.003 | 32.892 |
| 2026-10-12 | 6.3.0 | 9167 | 1158 | 0.0 | 1001.0 | 3216.0 | 1.425 | 3.987 | 34.613 |
| 2026-10-19 | 6.1.0 | 103 | 1 | 0.0 | 1056.0 | 2730.4 | 0.0 | 0.0 | 100.0 |
| 2026-10-19 | 6.1.1 | 772 | 117 | 13.212 | 952.0 | 3018.0 | 1.356 | 4.013 | 34.585 |
| 2026-10-19 | 6.3.0 | 10649 | 1289 | 0.0 | 996.0 | 3318.6 | 1.473 | 4.061 | 34.801 |

Quality and scope: receipt-only replays are collapsed before analysis. The canonical
warning join matches 99.952%; 152 warnings are unmatched.
150 matched warnings are outside drive intervals and excluded from
interval-valid warning rates. Zero observed warning counts can reflect incomplete
source reporting. Full API pagination does not establish complete attempted drives.
Late reports can revise weekly results; historical backdated receipts outside the
refresh overlap can be missed. Driver counts are not additive across versions.
See [metric_definitions.md](metric_definitions.md) for eligibility and exclusions.
