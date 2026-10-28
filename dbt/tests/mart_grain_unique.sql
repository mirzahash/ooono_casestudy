select reporting_week,platform,app_version,count(*) as row_count
from {{ ref('mart_weekly_release_health') }}
group by reporting_week,platform,app_version having count(*)<>1
