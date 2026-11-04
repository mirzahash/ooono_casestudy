-- What: Reports missing, fractional or below-one connection counts.
-- Why: Expose invalid counts excluded from the metric; warn without blocking the build.
{{ config(severity='warn') }}
select session_id, connection_count from {{ ref('stg_drives') }} where has_invalid_connection_count
