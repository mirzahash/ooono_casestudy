-- What: Reports missing/unparseable drive timestamps or an end before the start.
-- Why: Expose invalid drive intervals; warn without blocking the build.
{{ config(severity='warn') }}
select session_id from {{ ref('stg_drives') }}
where has_timestamp_parse_error or has_reversed_interval
