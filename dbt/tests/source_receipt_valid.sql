-- What: Checks that RAW drives and warnings have a nonnull receipt timestamp.
-- Why: The receipt cutoff needs a usable timestamp to decide which reports to include.
{% for table in ['drives','warnings'] %}
select '{{ table }}' as endpoint, report_key from {{ source('ooono_raw',table) }}
where source_received_at is null
{% if not loop.last %}union all{% endif %}
{% endfor %}
