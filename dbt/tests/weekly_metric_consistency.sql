with boundaries as (
    select min(started_at)::date as first_date, {{ monday('min(started_at)') }} as first_week,
        {{ monday("convert_timezone('Europe/Copenhagen', " ~ cutoff_literal() ~ ")::date") }} as current_week
    from {{ ref('int_drive_connection_behavior') }}
), expected as (
    select reporting_week,platform,app_version,count(*) as drives,count_if(is_multi_connection) as multi
    from {{ ref('int_drive_connection_behavior') }} cross join boundaries
    where is_eligible and reporting_week<current_week and (reporting_week>first_week or first_date=first_week)
    group by reporting_week,platform,app_version
), comparison as (
    select coalesce(e.reporting_week,m.reporting_week) as reporting_week,
           e.drives,e.multi,m.eligible_drives,m.multi_connection_drives
    from expected e full join {{ ref('mart_weekly_release_health') }} m using(reporting_week,platform,app_version)
)
select 'weekly_totals' as issue,reporting_week from comparison
where not equal_null(drives,eligible_drives) or not equal_null(multi,multi_connection_drives)
union all
select 'invalid_rate_or_bounds',reporting_week from {{ ref('mart_weekly_release_health') }}
where eligible_drives<=0 or multi_connection_drives<0 or multi_connection_drives>eligible_drives
    or multi_connection_share is null or multi_connection_share not between 0 and 1
    or abs(multi_connection_share-multi_connection_drives::float/eligible_drives)>0.000000001
    or drivers_with_multiple_connections<0 or drivers_with_multiple_connections>distinct_drivers
    or distinct_drivers>eligible_drives
