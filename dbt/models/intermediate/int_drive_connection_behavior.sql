-- Grain: one canonical drive. Warning events are aggregated before the final join.
with matched_warnings as (
    select w.session_id,
        w.has_timestamp_parse_error, w.has_future_device_clock,
        w.device_time between d.started_at and d.ended_at as is_interval_valid,
        w.user_id is not null and d.user_id is not null and w.user_id<>d.user_id as has_user_mismatch
    from {{ ref('stg_warnings') }} w join {{ ref('stg_drives') }} d using(session_id)
), warning_totals as (
    select session_id, count(*) as warning_count,
        count_if(is_interval_valid) as interval_valid_warning_count,
        count_if(not coalesce(is_interval_valid,false)) as warning_clock_anomaly_count,
        count_if(has_future_device_clock) as future_warning_clock_count,
        count_if(has_user_mismatch) as warning_user_mismatch_count
    from matched_warnings group by session_id
), enriched as (
    select d.*,
        coalesce(w.warning_count,0) as warning_count,
        coalesce(w.interval_valid_warning_count,0) as interval_valid_warning_count,
        coalesce(w.warning_clock_anomaly_count,0) as warning_clock_anomaly_count,
        coalesce(w.future_warning_clock_count,0) as future_warning_clock_count,
        coalesce(w.warning_user_mismatch_count,0) as warning_user_mismatch_count,
        {{ monday('d.started_at') }} as reporting_week,
        d.connection_count>1 as is_multi_connection,
        not (d.has_timestamp_parse_error or d.has_reversed_interval or d.has_invalid_duration
             or d.has_invalid_connection_count or d.has_duration_mismatch) as is_eligible
    from {{ ref('stg_drives') }} d left join warning_totals w using(session_id)
)
select *, warning_clock_anomaly_count>0 as has_warning_clock_anomaly,
    warning_user_mismatch_count>0 as has_warning_user_mismatch,
    reporting_week = {{ monday('min(started_at) over ()') }}
        and min(started_at) over ()::date <> {{ monday('min(started_at) over ()') }} as is_partial_source_boundary_week,
    {{ cutoff_literal() }} as analysis_receipt_cutoff
from enriched
