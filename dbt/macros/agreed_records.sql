{% macro agreed_records(source_table, receipt_filter=true) %}
with scoped as (
    select * from {{ source('ooono_raw', source_table) }}
    where snapshot_id = {{ snapshot_literal() }}
    {% if receipt_filter %}and source_received_at <= {{ cutoff_literal() }}{% endif %}
), identities as (
    select source_id,
        count(distinct to_json(object_delete(payload, 'received_at'))) as business_versions,
        min(source_received_at) as first_received_at,
        max(source_received_at) as last_received_at,
        count(*) as report_count
    from scoped where source_id is not null group by source_id
), agreed as (
    select s.*, i.first_received_at, i.last_received_at, i.report_count
    from scoped s join identities i on s.source_id=i.source_id
    where i.business_versions=1
    qualify row_number() over(partition by s.source_id order by s.source_received_at nulls last, s.source_ordinal)=1
)
{% endmacro %}
