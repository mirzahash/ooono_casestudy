-- What: Reports missing/unparseable warning times or times outside a matched drive interval.
-- Why: Expose warning-clock problems without discarding warnings; warn only.
{{ config(severity='warn') }}
select w.warning_id
from {{ ref('stg_warnings') }} w left join {{ ref('stg_drives') }} d using(session_id)
where w.has_timestamp_parse_error
    or (d.session_id is not null and (w.device_time<d.started_at or w.device_time>d.ended_at))
