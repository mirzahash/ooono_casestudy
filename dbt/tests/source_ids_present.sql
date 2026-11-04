-- What: Checks that reports in scope have a source ID.
-- Why: Every report needs an ID to be assigned to a session, warning or user.
-- Missing source IDs cannot be assigned to a session, warning or user.
{% for table in ['drives','warnings','users'] %}
select '{{ table }}' as source_table, source_id, count(*) as report_count
from {{ source('ooono_raw', table) }}
{% if table != 'users' %}where source_received_at <= {{ cutoff_literal() }}{% endif %}
group by source_id
having source_id is null
{% if not loop.last %}union all{% endif %}
{% endfor %}
