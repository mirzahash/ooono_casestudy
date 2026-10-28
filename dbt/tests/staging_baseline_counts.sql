-- depends_on: {{ ref('stg_drives') }}
-- depends_on: {{ ref('stg_warnings') }}
-- depends_on: {{ ref('stg_users') }}
{% if reference_baseline() %}
with checks as (
    select 'canonical_sessions' as metric, count(*) as actual, 219848 as expected from {{ ref('stg_drives') }}
    union all select 'warnings',count(*),315601 from {{ ref('stg_warnings') }}
    union all select 'users',count(*),3085 from {{ ref('stg_users') }}
    union all select 'collapsed_receipts',sum(report_count-1),4346 from {{ ref('stg_drives') }}
    union all select 'cutoff_drive_reports',count(*),224194 from {{ source('ooono_raw','drives') }}
      where snapshot_id={{ snapshot_literal() }} and source_received_at<={{ cutoff_literal() }}
    union all select 'raw_drive_rows',count(*),224200 from {{ source('ooono_raw','drives') }} where snapshot_id={{ snapshot_literal() }}
    union all select 'raw_warning_rows',count(*),315614 from {{ source('ooono_raw','warnings') }} where snapshot_id={{ snapshot_literal() }}
)
select * from checks where actual<>expected
{% else %}
select 'reference_not_applicable' as metric where false
{% endif %}
