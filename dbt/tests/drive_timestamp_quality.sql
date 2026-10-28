{{ config(severity='warn') }}
select session_id from {{ ref('stg_drives') }}
where has_timestamp_parse_error or has_reversed_interval or has_future_device_clock or has_duration_mismatch
