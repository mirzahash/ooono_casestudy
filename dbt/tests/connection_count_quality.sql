{{ config(severity='warn') }}
select session_id, connection_count from {{ ref('stg_drives') }} where has_invalid_connection_count
