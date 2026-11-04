-- What: Compares intermediate session, warning, anomaly and eligibility totals with the original baseline.
-- Why: Detect changes to historical drive enrichment during a controlled baseline replay.
-- Scope: runs only with validate_baseline=true and the original baseline data/cutoff.
-- With the default false setting, this test returns no rows without checking counts.
-- depends_on: {{ ref('int_drive_connection_behavior') }}
{% if reference_baseline() %}
with checks as (
    select 'sessions' as metric,count(*) as actual,219848 as expected from {{ ref('int_drive_connection_behavior') }}
    union all select 'matched_warnings',sum(warning_count),315449 from {{ ref('int_drive_connection_behavior') }}
    union all select 'outside_warning_intervals',sum(warning_clock_anomaly_count),150 from {{ ref('int_drive_connection_behavior') }}
    union all select 'ineligible_drives',count_if(not is_eligible),0 from {{ ref('int_drive_connection_behavior') }}
    union all select 'warning_user_mismatches',sum(warning_user_mismatch_count),0 from {{ ref('int_drive_connection_behavior') }}
)
select * from checks where coalesce(actual,0)<>expected
{% else %}
select 'reference_not_applicable' as metric where false
{% endif %}
