select 'snapshot_not_complete_or_wrong_purpose' as issue
where (select count(*) from {{ source('ooono_raw','ingestion_snapshots') }}
       where snapshot_id={{ snapshot_literal() }} and status='COMPLETE'
       and manifest:identity:purpose::varchar='FULL_BASELINE') <> 1
