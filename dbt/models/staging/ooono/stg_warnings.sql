-- Grain: one agreeing warning_id; unmatched/invalid-clock warnings are retained.
{{ agreed_records('warnings') }}
, typed as (
    select source_id as warning_id, payload:session_id::varchar as session_id,
        payload:user_id::varchar as user_id, payload:pin_type::varchar as pin_type,
        payload:user_action::varchar as user_action,
        payload:device_time::varchar as device_time_raw,
        try_to_timestamp_ntz(payload:device_time::varchar) as device_time,
        first_received_at, last_received_at, report_count,
        snapshot_id, source_ordinal, record_hash, source_file, source_file_sha256, ingested_at
    from agreed
)
select *, device_time is null as has_timestamp_parse_error,
    coalesce(device_time > dateadd(day,2,{{ cutoff_literal() }}::timestamp_ntz),false) as has_future_device_clock
from typed
