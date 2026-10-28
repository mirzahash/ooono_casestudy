select c.reporting_week,c.platform,c.app_version
from {{ ref('mart_weekly_release_health') }} c
left join {{ ref('mart_weekly_release_health') }} p
 on c.platform=p.platform and c.app_version=p.app_version and p.reporting_week=dateadd(week,-1,c.reporting_week)
where not equal_null(c.previous_week_eligible_drives,p.eligible_drives)
 or not equal_null(c.previous_week_multi_connection_share,p.multi_connection_share)
 or (p.reporting_week is null and (c.multi_connection_share_wow_pp is not null or c.eligible_drives_wow_pct is not null))
 or (p.reporting_week is not null and abs(c.multi_connection_share_wow_pp-100.0*(c.multi_connection_share-p.multi_connection_share))>0.000000001)
