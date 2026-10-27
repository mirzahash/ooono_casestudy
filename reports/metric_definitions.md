# Provisional weekly connection behavior

Status: proposed descriptive metric for review. It does not establish a failed,
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
