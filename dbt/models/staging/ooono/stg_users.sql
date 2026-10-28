-- Grain: one agreeing user_id in the chosen current-state snapshot, not historical plans.
{{ agreed_records('users', false) }}
, typed as (
    select source_id as user_id, payload:created_at::varchar as created_at_raw,
        try_to_timestamp_ntz(payload:created_at::varchar) as created_at,
        payload:country::varchar as country, payload:platform::varchar as platform,
        payload:plan::varchar as plan,
        try_to_decimal(payload:monthly_price_eur::varchar,18,2) as monthly_price_eur,
        first_received_at, last_received_at, report_count,
        snapshot_id, source_ordinal, record_hash, source_file, source_file_sha256, ingested_at
    from agreed
)
select *, created_at is null as has_timestamp_parse_error from typed
