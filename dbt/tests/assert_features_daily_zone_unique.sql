-- Teste singular: o grão de features_daily_zone é (zone_id, trip_date).
-- dbt não tem teste nativo de unicidade composta sem dbt_utils, que o projeto não usa.
select
    zone_id,
    trip_date,
    count(*) as n
from {{ ref('features_daily_zone') }}
group by 1, 2
having count(*) > 1
