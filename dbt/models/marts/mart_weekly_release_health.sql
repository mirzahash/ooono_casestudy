-- Grain: complete reporting week x platform x app version; device wall-calendar dates.
with boundaries as (
    select min(started_at)::date as first_observed_date,
        {{ monday('min(started_at)') }} as first_observed_week,
        {{ monday("convert_timezone('Europe/Copenhagen', " ~ cutoff_literal() ~ ")::date") }} as current_reporting_week
    from {{ ref('int_drive_connection_behavior') }}
), eligible as (
    select d.* from {{ ref('int_drive_connection_behavior') }} d cross join boundaries b
    where d.is_eligible and d.reporting_week < b.current_reporting_week
      -- Do not publish the known partial first source-calendar week.
      and (d.reporting_week > b.first_observed_week or b.first_observed_date=b.first_observed_week)
), weekly as (
    select reporting_week, platform, app_version,
        count(*) as eligible_drives,
        count_if(is_multi_connection) as multi_connection_drives,
        count_if(is_multi_connection)::float / count(*) as multi_connection_share,
        count(distinct user_id) as distinct_drivers,
        count(distinct case when is_multi_connection then user_id end) as drivers_with_multiple_connections,
        median(duration_s) as median_duration_s,
        percentile_cont(0.95) within group(order by duration_s) as p95_duration_s,
        percentile_cont(0.95) within group(order by connection_count) as p95_connection_count,
        sum(duration_s)/3600.0 as driving_hours,
        sum(warning_count) as observed_warnings,
        sum(interval_valid_warning_count) as interval_valid_warnings,
        sum(interval_valid_warning_count)/nullif(sum(duration_s)/3600.0,0) as valid_warnings_per_drive_hour,
        min(snapshot_id) as snapshot_id,
        min(analysis_receipt_cutoff) as analysis_receipt_cutoff
    from eligible group by reporting_week, platform, app_version
)
select c.*,
    p.eligible_drives as previous_week_eligible_drives,
    p.multi_connection_share as previous_week_multi_connection_share,
    c.eligible_drives-p.eligible_drives as eligible_drives_wow_change,
    100.0*(c.eligible_drives::float/nullif(p.eligible_drives,0)-1) as eligible_drives_wow_pct,
    100.0*(c.multi_connection_share-p.multi_connection_share) as multi_connection_share_wow_pp,
    100.0*(c.distinct_drivers::float/nullif(p.distinct_drivers,0)-1) as distinct_drivers_wow_pct
from weekly c left join weekly p
    on c.platform=p.platform and c.app_version=p.app_version
    and p.reporting_week=dateadd(week,-1,c.reporting_week)
