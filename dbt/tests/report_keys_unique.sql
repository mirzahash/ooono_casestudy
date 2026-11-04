-- What: Checks that RAW report keys are present and unique within each source table.
-- Why: Detect duplicate report loading or missing report keys.
{% for table in ['drives','warnings','users'] %}
select '{{ table }}' as source_table, report_key
from {{ source('ooono_raw',table) }}
group by report_key having report_key is null or count(*)<>1
{% if not loop.last %}union all{% endif %}
{% endfor %}
