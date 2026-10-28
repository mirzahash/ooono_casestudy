-- depends_on: {{ ref('mart_weekly_release_health') }}
{% if reference_baseline() %}
with expected as (
    select column1::date as reporting_week,column2::varchar as platform,column3::number as drives,column4::number as multi
    from values ('2026-10-12','android',10093,1287),('2026-10-12','ios',11618,232),
                ('2026-10-19','android',10071,1320),('2026-10-19','ios',11524,102),
                ('2026-10-12','all',21711,1519),('2026-10-19','all',21595,1422)
), actual as (
    select reporting_week,platform,sum(eligible_drives) as drives,sum(multi_connection_drives) as multi
    from {{ ref('mart_weekly_release_health') }} where reporting_week in ('2026-10-12','2026-10-19')
    group by reporting_week,platform
    union all
    select reporting_week,'all',sum(eligible_drives),sum(multi_connection_drives)
    from {{ ref('mart_weekly_release_health') }} where reporting_week in ('2026-10-12','2026-10-19') group by reporting_week
)
select coalesce(e.reporting_week,a.reporting_week) as reporting_week,coalesce(e.platform,a.platform) as platform,
    e.drives as expected_drives,a.drives as actual_drives,e.multi as expected_multi,a.multi as actual_multi
from expected e full join actual a using(reporting_week,platform)
where not equal_null(e.drives,a.drives) or not equal_null(e.multi,a.multi)
{% else %}
select 'reference_not_applicable' as metric where false
{% endif %}
