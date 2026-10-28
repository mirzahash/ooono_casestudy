{% for table in ['drives','warnings'] %}
select '{{ table }}' as endpoint, source_ordinal from {{ source('ooono_raw',table) }}
where snapshot_id={{ snapshot_literal() }} and source_received_at is null
{% if not loop.last %}union all{% endif %}
{% endfor %}
