# Approved dbt Core implementation

Implemented and validated on 28 October 2026. Core 1.12.6 / adapter 1.12.4 are isolated
in Python 3.12; five models and 28 data tests run under OOONO_DBT. See
`reports/dbt_validation.md` for final evidence. RAW and ingestion dependencies remain
unchanged. Snapshot ID and receipt cutoff are configurable vars, defaulting to the
approved frozen baseline; there is no automatic latest-snapshot selection.

## Scope and dependencies

Use the Python-based dbt Core runtime with dbt-snowflake, pinned to a mutually
compatible pair after checking dependency resolution. The existing environment is
Python 3.14.6 with snowflake-connector-python 5.1.0; dbt is not installed. Verify
adapter compatibility rather than forcing a conflicting upgrade/downgrade of the
working ingestion environment. If necessary, isolate dbt in .venv-dbt using a
supported available Python, with requirements-dbt.txt. Do not install a different
dbt runtime merely because it is newer. No dbt packages such as dbt-utils are
required for five models and a few focused SQL tests.

## Proposed layout

```text
dbt/
  dbt_project.yml
  profiles.yml.example
  models/
    staging/ooono/
      _ooono__sources.yml
      _ooono__models.yml
      stg_drives.sql
      stg_warnings.sql
      stg_users.sql
    intermediate/
      int_drive_connection_behavior.sql
      intermediate.yml
    marts/
      mart_weekly_release_health.sql
      marts.yml
  macros/
  tests/                         # singular dbt tests
requirements-dbt.txt
sql/dbt_setup.sql
scripts/run_dbt.py
 tests/test_ingestion.py           # repository-level Python tests
```

Use a small wrapper because dbt env_var reads process environment variables but
does not automatically load the project's .env file. dbt debug/build go through
that wrapper; it never prints credentials. Local dbt/profiles.yml, .venv-dbt/, dbt/target/,
dbt/logs/, and dbt/dbt_packages/ are ignored. The example profile is safe to commit.

The scoped schema macro targets exactly STAGING for staging/intermediate models
and ANALYTICS for marts in this single-user case. Avoid dbt's default custom-schema
prefix accidentally creating STAGING_ANALYTICS. Guard the configured mappings;
RAW is never an output schema. If multiple developers are added later, restore
isolated development schemas instead of sharing these case-study schemas.

## Snowflake role and authentication

Create OOONO_DBT with:

- USAGE on OOONO_WH and OOONO_CASE.
- USAGE on RAW; SELECT on DRIVES, WARNINGS, USERS, and INGESTION_SNAPSHOTS only.
- USAGE and CREATE TABLE / CREATE VIEW on STAGING and ANALYTICS.
- Ownership of its newly built models through their creation under OOONO_DBT.
- Assignment to the existing user object, using CURRENT_USER() to avoid confusing
  the object name with LOGIN_NAME during grants.

No INSERT/UPDATE/DELETE on RAW, no ingestion-stage access, no broad future RAW
write grants, and no ACCOUNTADMIN for dbt debug/build. A privileged role is used
only for one-time additive setup; keep OOONO_INGESTOR unchanged. Existing STAGING
and ANALYTICS schemas are verified and reused; create only if absent. An initial
permission check confirms dbt can create/drop its own models in those schemas.

Reuse registered encrypted key-pair authentication. The profile uses env_var for
account, confirmed LOGIN_NAME, warehouse, key path/passphrase, and a distinct
DBT_SNOWFLAKE_ROLE=OOONO_DBT setting. Do not change SNOWFLAKE_ROLE, which ingestion
uses. Use UTC session receipt handling, deterministic week expressions, and two
threads to keep warehouse use modest.

## Frozen inputs

Pin dbt vars to the approved FULL_BASELINE ID:
`e943b3aefc3411575c251ada7404c7013b54bf9510e8d37e9e69bd2f80bf863a`.
Pin receipt cutoff to `2026-10-27T15:21:56.773109+00:00` and derive the reporting
calendar/as-of date from that cutoff in Europe/Copenhagen, not CURRENT_DATE.
A test verifies the ID is complete and its manifest purpose is FULL_BASELINE.

Read all three endpoints from that ID only. Exclude SMALL_TEST and every other
snapshot explicitly. Apply the receipt cutoff to drives/warnings BEFORE business
agreement checks and deduplication. This selects 224,194 of 224,200 RAW drives and
315,601 of 315,614 warnings. The six drive and 13 warning receipts after cutoff
remain untouched in RAW. Users have no source received_at: use their full capture
of 3,085 rows, with their later capture window documented. Current plan is not
historical plan and is not used for financial attribution.

## Models and grains

| Model | Schema / materialization | Grain and behavior |
| --- | --- | --- |
| stg_drives | STAGING / view | One canonical session_id after agreeing-business-payload collapse; first/last receipt and report count retained |
| stg_warnings | STAGING / view | One agreeing warning_id, with session_id, clock/action/type fields and receipt lineage |
| stg_users | STAGING / view | One agreeing user_id within the chosen current-state snapshot |
| int_drive_connection_behavior | STAGING / table | One canonical session, warning aggregates, eligibility and quality flags |
| mart_weekly_release_health | ANALYTICS / table | Reporting week x platform x app version, only eligible sessions in complete calendar weeks |

Views keep source normalization transparent. Full-rebuild tables avoid repeatedly
running canonicalization/join work in downstream queries; at approximately 540k
source event reports no incremental dbt strategy is warranted. dbt rebuilds only
its own derived relations; RAW is append-only and remains untouched.

Business agreement compares the complete original payload minus received_at,
BEFORE casting (so casts cannot hide differences). Session ID alone is not enough.
Agreeing replays collapse to a representative business record plus MIN/MAX receipt
and report_count. Missing IDs and differing business payloads are excluded from
canonical outputs, surfaced by failing source-identity tests and explicit counts;
no silent latest-wins rule. RAW retains every original record. A source diagnostic
query shows excluded identities. Current baseline has zero such conflicts.

TRY_* casts preserve rows with invalid values as NULL plus anomaly flags, not
silent WHERE filters. Keep original timestamp strings, TIMESTAMP_NTZ device times,
TIMESTAMP_TZ receipts, record/snapshot lineage, and parse/missingness flags.
Numeric casts must not round fractional counts/durations into valid integers:
check integrality before accepted count validation. Unknown platform/version
categories stay explicit. Zero/negative durations and inconsistent intervals are
flagged; only metric eligibility excludes them.

Device clocks remain naive local-wall values, not guessed UTC. Week start is
Monday from device started_at, using an expression independent of session WEEK_START.
Warning future clocks and out-of-drive-interval clocks are flagged and retained.
Null user_action remains null, not "ignored" or "failed".

## Dependency graph and drive-level join

```text
RAW.DRIVES   -> stg_drives   --+
RAW.WARNINGS -> stg_warnings --+-> int_drive_connection_behavior -> mart_weekly_release_health
RAW.USERS    -> stg_users        (documented standalone current-state dimension)
RAW.INGESTION_SNAPSHOTS -> snapshot validation / fixed-source selection
```

Do not join current user plan into historical drive metrics. Use stg_users for
source reconciliation and optional referential-quality checks only.

Inside int_drive_connection_behavior, join canonical warnings to canonical drives
with a validated many-to-one relationship, assess interval/user flags, aggregate
by session_id, then left join that one-row-per-session aggregate to drives.
Never join event-level warnings directly into the drive-counting output.

Keep warning_count, interval_valid_warning_count, clock/anomaly count, user mismatch
count, and quality indicators. Zero counts mean zero observed matching records.
The 152 unmatched warnings remain in stg_warnings and a warning-level diagnostic;
they are not dropped from staging or attached to arbitrary drives. The 150
out-of-interval warnings remain flagged and excluded only from the valid-warning
numerator. No cartesian fan-out and no warning filter applied to drive eligibility.

Drive eligibility exactly follows metric_definitions.md: parseable start/end,
nonnegative elapsed time, positive numeric duration within one second of elapsed,
and integer connection_count >=1. Multi-connection means >1, not confirmed failure.
The int model retains ineligible canonical sessions with flags.

## Weekly mart and changes

Include eligible_drives, multi_connection_drives, multi_connection_share as a 0–1
ratio, distinct_drivers, and drivers_with_multiple_connections (descriptive affected
driver count). Include median/p95 duration and p95 connection count, with source
cutoff/snapshot metadata. A rendered percentage is share x100. Preserve per-group
numerators/denominators so overall rate is SUM(numerator)/SUM(denominator), not the
average of platform/version rates.

WoW compares the immediately previous calendar week within the SAME platform and
version. Guard week adjacency: new versions or missing previous weeks produce NULL,
not zero and not a comparison against the last arbitrary available row. Include
percentage-point rate change and relative drive/driver volume changes with zero
previous denominators yielding NULL. Distinct drivers cannot be summed across
platform/version groups; use the int model for overall distinct-driver totals.

Current incomplete week is excluded relative to the fixed analysis cutoff. Flag
known lower-edge source coverage and do not call an initial partially observed
week fully covered. Exclude that boundary week from Product comparisons. Late
arrivals still mean a complete calendar week is not a guaranteed complete cohort.
No release-causality or confirmed failure labels are introduced.

## Tests and notebook reconciliation

Blocking tests:

- Nonnull and unique canonical session IDs; unique warning/user IDs.
- Missing-ID/business-payload conflicts at the selected RAW scope.
- int session IDs refer to stg_drives and retain exactly one row per session.
- Valid count/eligibility consistency; multi indicator only follows count >1.
- Unique mart week/platform/version combination and nonnull grain fields.
- Numerator <= denominator, ratio 0–1, share arithmetic, and driver count bounds.
- Weekly sums reconcile to eligible int drives without warning fan-out.
- Snapshot manifest COMPLETE/purpose, source counts, canonical counts, frozen weeks.

Known anomalies are explicit warning-severity tests/flags: orphan warnings (152),
out-of-interval clocks (150), and any unverified current-users referential gaps.
Do not add a strict generic warning->drive relationship test that predictably fails
for the known orphans. Canonical timestamp anomalies remain visible; they only fail
metric consistency if they incorrectly enter the eligible denominator.

Baseline targets:

| Metric | 12–18 October | 19–25 October |
| --- | ---: | ---: |
| Eligible drives | 21,711 | 21,595 |
| Multi-connection drives | 1,519 | 1,422 |
| Overall share | 6.996% (7.00%) | 6.585% (6.59%) |
| Android drives / multi drives | 10,093 / 1,287 | 10,071 / 1,320 |
| Android share | 12.751% | 13.107% |
| iOS drives / multi drives | 11,618 / 232 | 11,524 / 102 |
| iOS share | 1.997% | 0.885% |

Also require 219,848 canonical sessions, 4,346 collapsed receipt-only reports,
315,601 canonical warnings, 315,449 matching warnings, and zero baseline drive
eligibility exclusions. Counts/numerators are compared exactly; rates use numeric
tolerance before display rounding. Reference tests are explicitly scoped to this
baseline; new snapshots require revised references rather than passing old totals.

## Implementation sequence after approval

1. Resolve compatible Core/adapter dependencies without breaking ingestion; pin.
2. Add project/profile wrapper and scoped role grants; run dbt debug.
3. Build/test the three staging models and validate counts/flags.
4. Build/test the drive-level table with preaggregated warnings.
5. Build/test weekly mart and all frozen-baseline/platform reconciliations.
6. Document results and update the stale project-context status.

No Steep implementation, packages framework, incremental dbt, orchestration, or
additional exploratory notebooks. Implementation complete; no Steep work started.

References: [Python compatibility](https://docs.getdbt.com/faqs/Core/install-python-compatibility),
[custom schema behavior](https://docs.getdbt.com/docs/build/custom-schemas).

## Repository boundary

The dbt project now lives in `dbt/`, separate from Python ingestion and reports.
The runner passes `--project-dir` explicitly. This is a repository organization
choice, not a dbt requirement that projects must use that directory name. See
`dbt/README.md` for the official documentation and the retained canonical-staging
convention. Model SQL, grains, schemas, and baseline definitions are unchanged.
