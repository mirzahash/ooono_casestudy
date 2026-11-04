# dbt design

RAW.DRIVE_REPORTS → stg_drives ───┐
                                ├→ int_drive_connection_behavior → mart_weekly_release_health
RAW.WARNING_REPORTS → stg_warnings┘
RAW.USER_PROFILES → stg_users (current-state users; not joined into weekly metrics)

Staging uses views to type payloads and keep the earliest received report per ID.
Repeated baseline reports agreed on business fields; no conflicts were observed.
This selection order is not a claim about how future session updates should work.
Timestamp anomalies stay flagged. The drive table aggregates warnings before the
join, preserving one row per canonical drive. The mart groups complete weeks by
platform/version and computes adjacent-week comparisons. Both are rebuilt tables
at the case-study scale; no incremental dbt processing is claimed.

Pipeline variables are run_id and receipt_cutoff. There is no source snapshot
filter. Standalone build uses the last successful INGESTION_RUNS entry. The legacy
mart SNAPSHOT_ID column retains its name/type but now labels the analytical run.
Mart expressions and column order are preserved. Eligibility uses basic value checks;
no duration-to-interval tolerance or future-clock threshold is applied.

OOONO_DBT has RAW SELECT and model creation permissions. The mart's configured
SELECT grant is reapplied to STEEP_READONLY during build. Reference-only baseline
checks require explicit validate_baseline=true; generic tests always run.

The first observed week is retained even if its first drive is after Monday.
No missing-data inference is made from the earliest observed drive date.
