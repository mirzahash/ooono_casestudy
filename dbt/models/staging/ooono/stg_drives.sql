-- Grain: one session, represented by its earliest received report.
{{ agreed_records('drives') }}
, typed as (
    select source_id as session_id, 
        payload:user_id::varchar as user_id,
        coalesce(payload:platform::varchar, 'unknown') as platform,
        coalesce(payload:app_version::varchar, 'unknown') as app_version,
        payload:os_version::varchar as os_version,
        payload:device::varchar as device, payload:country::varchar as country,
        payload:started_at::varchar as started_at_raw,
        payload:ended_at::varchar as ended_at_raw,
        try_to_timestamp_ntz(payload:started_at::varchar) as started_at,
        try_to_timestamp_ntz(payload:ended_at::varchar) as ended_at,
        payload:duration_s::varchar as duration_s_raw,
        payload:connection_count::varchar as connection_count_raw,
        try_to_double(payload:duration_s::varchar) as duration_s,
        try_to_double(payload:connection_count::varchar) as connection_count,
        first_received_at, last_received_at, report_count,
        {{ run_id_literal() }}::varchar as snapshot_id, report_key, record_hash, source_file, ingested_at
    from agreed
)
select *,
    started_at is null or ended_at is null as has_timestamp_parse_error,
    coalesce(ended_at < started_at, false) as has_reversed_interval,
    duration_s is null or duration_s <= 0 as has_invalid_duration,
    connection_count is null or connection_count < 1 or mod(connection_count,1) <> 0 as has_invalid_connection_count
from typed
