-- What: Reports warnings that have no matching drive in staging.
-- Why: Show warnings that cannot currently be attached to a drive; warn only.
{{ config(severity='warn') }}
select w.warning_id, w.session_id
from {{ ref('stg_warnings') }} w left join {{ ref('stg_drives') }} d using(session_id)
where d.session_id is null
