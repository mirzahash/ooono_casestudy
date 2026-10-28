with counts as (
    select (select count(*) from {{ ref('stg_drives') }}) as staging_count,
           (select count(*) from {{ ref('int_drive_connection_behavior') }}) as drive_count
)
select 'drive_count_changed' as issue where (select staging_count<>drive_count from counts)
union all
select 'invalid_drive_entered_denominator' from {{ ref('int_drive_connection_behavior') }}
where is_eligible and (has_timestamp_parse_error or has_reversed_interval or has_invalid_duration
    or has_invalid_connection_count or has_duration_mismatch)
union all
select 'indicator_or_warning_count_invalid' from {{ ref('int_drive_connection_behavior') }}
where not equal_null(is_multi_connection,connection_count>1)
    or warning_count<0 or interval_valid_warning_count<0 or interval_valid_warning_count>warning_count
union all
select 'warning_fanout_or_loss'
where (select sum(warning_count) from {{ ref('int_drive_connection_behavior') }}) <>
      (select count(*) from {{ ref('stg_warnings') }} w join {{ ref('stg_drives') }} d using(session_id))
