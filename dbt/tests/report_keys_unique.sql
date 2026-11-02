{% for table in ['drives','warnings','users'] %}
select '{{ table }}' as source_table, report_key
from {{ source('ooono_raw',table) }}
group by report_key having report_key is null or count(*)<>1
{% if not loop.last %}union all{% endif %}
{% endfor %}
