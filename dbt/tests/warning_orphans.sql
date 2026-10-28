{{ config(severity='warn') }}
select w.warning_id, w.session_id
from {{ ref('stg_warnings') }} w left join {{ ref('stg_drives') }} d using(session_id)
where d.session_id is null
