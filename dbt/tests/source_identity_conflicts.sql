-- No latest-wins fallback; missing IDs/conflicts are visible blocking exceptions.
{% for table in ['drives','warnings','users'] %}
select '{{ table }}' as source_table, source_id, count(*) as report_count
from {{ source('ooono_raw', table) }}
where snapshot_id={{ snapshot_literal() }}
{% if table != 'users' %}and source_received_at <= {{ cutoff_literal() }}{% endif %}
group by source_id
having source_id is null or count(distinct to_json(object_delete(payload,'received_at')))>1
{% if not loop.last %}union all{% endif %}
{% endfor %}
