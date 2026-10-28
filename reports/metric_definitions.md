# Metric definitions — case-study descriptive MVP

Status: finalized calculation contract for the descriptive MVP, subject to the
explicit source-semantic assumptions below. It does not establish a failed,
interrupted, or bad drive. The source does not expose an explicit outcome flag.

## Canonical session

Compare every drive field except `received_at` for each nonnull `session_id`.
If those business fields agree, retain one session, the earliest observed receipt,
latest observed receipt, and report count. Exclude business-field conflicts and
missing IDs from the canonical dataset and report their counts. Apply the same
identity check to `warning_id`. Do not sum warnings after a fan-out join.

## Metric definition

- Numerator: eligible canonical reported sessions with `connection_count > 1`.
- Denominator: canonical reported sessions with parseable start/end, nonnegative
  elapsed time, positive numeric duration agreeing with elapsed time within one
  second, and an integer connection count of at least one.
- Unit: percent of eligible reported sessions; show numerator and denominator.
- Context: reported drive count, distinct drivers, distinct drivers with a
  multiple-connection session, median duration, and connection-count p95.
- Breakdowns: platform and app version; inspect device and duration mix.
- Missing platform/version: retain an explicit unknown category.
- Invalid duration/count/time: exclude from the metric, show exclusion counts;
  do not recode missing values as zero.
- Unreported sessions: unavailable and outside the denominator. We cannot infer
  failed attempts or ongoing sessions from their absence.

## Time and completeness

Use `started_at` to assign provisional Monday–Sunday device wall-calendar weeks.
Offsets are absent, so this is not a confirmed UTC or Copenhagen event-time
metric. Country alone does not establish a device timezone. Copenhagen time is
used to determine the current reporting date and select the preceding two
calendar weeks; the current week is excluded.

The notebook displays a +/-2-hour clock-shift sensitivity check, not a timezone
conversion. Compare device end clock with UTC receipt clock only as an offset/lag
diagnostic, not latency. Warning clock anomalies are checked separately.

Apply the saved `scope.json` UTC receipt cutoff before deduplication. Prior weeks
may change as reports arrive. Show first-observed receipts after the following
Monday and data freshness. A complete calendar week is not necessarily a fully
arrived cohort. The incremental cache refresh has a 24-hour overlap and cannot
guarantee capture of older backdated receipts or deletions.

## Interpretation

A change indicates different recorded connection behavior. It may reflect drive
duration, device/platform mix, rollout population, or instrumentation. It is not
proof of release causality or worse driver experience. Distinct-driver counts
are not additive across releases. Warning frequency and null reactions do not
measure missed alerts or failure without expected-warning or outcome evidence.

Before using this as a confirmed product-health KPI, validate timestamp semantics
and connection-count meaning with the source owner. Until then, present findings
as provisional signals and explicitly state that worse driver experience cannot
be concluded from these fields alone.

## Supporting duration and warning measures

Duration context is the median and p95 of `duration_s` over the same eligible,
canonical sessions; use seconds, not receipt-clock differences. All-history and
same-week version comparisons are displayed separately to expose calendar mix.

Warning identity is `warning_id`; collapse only agreeing business records as
above, retaining receipt metadata. Join warnings to canonical sessions using a
validated many-to-one `session_id` join. Apply the same saved receipt cutoff to
both inputs. Count unmatched warnings separately, never attach them arbitrarily.

- Matched warnings per drive: count of canonical matched warnings divided by
  eligible canonical drives, including drives with zero observed warnings.
- Interval-valid warnings per drive-hour: count of matched warnings whose parsed
  `device_time` lies within the inclusive drive start/end interval, divided by
  total eligible drive duration in hours. Unparseable/out-of-interval warning
  clocks are excluded from this numerator and counted as quality exceptions.
- Zero observed warning share: eligible drives with no matched warning record,
  divided by eligible drives. This describes observed records, not missed alerts.

Assume timestamps within one joined session use comparable wall clocks for the
interval check; this is not a timezone conversion or a guarantee of clock accuracy.
Driving hours are an exposure proxy, not the number of expected alerts. Routes,
geography, warning availability, duration, drivers, and rollout mix can explain
differences. Do not interpret absent reactions as dissatisfaction or failure.

## Final interpretation for iOS 6.3.0

All 26,367 eligible 6.3.0 sessions in the frozen extract have a count of exactly
one across every observed device category. Treat the field as potentially
noncomparable across versions until its semantics/instrumentation are confirmed.
Do not publish a zero-failure claim or describe aggregate improvement as improved
experience. The `device` field describes CO-DRIVER categories, not handset models.
The same-week 6.1.0 comparison includes only one driver per week; it is descriptive
and not a representative release baseline. The 6.1.1 population is also changing.

## Frozen analysis inputs

Notebook 04 reads `data/analysis_snapshot_20261027/`, reconstructed offline from
the completed baseline and completed refresh after the active profiling cache was
found incomplete. Its local manifest records source and reconstructed checksums.
Receipt cutoff: `2026-10-27T15:21:56.773109+00:00`.
224,194 drive reports reduce to 219,848 canonical sessions; 315,601 canonical
warnings remain. There are no observed business-field conflicts. All canonical
sessions pass the stated numeric/time eligibility rules in this snapshot.

These rules and counts refer to this snapshot, not a claim about future data.
Revalidate eligibility/conflicts on each new snapshot. Week comparisons use
12–18 and 19–25 October 2026, excluding the current incomplete calendar week.
