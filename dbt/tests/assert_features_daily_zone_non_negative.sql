-- Teste singular: nenhuma feature agregada pode ser negativa.
-- (trips/revenue vêm de agg_daily_demand, que já filtra is_valid_trip; este teste
-- protege contra mudança futura na agregação, não contra a fonte.)
select *
from {{ ref('features_daily_zone') }}
where trips < 0
   or revenue < 0
   or trips_7d_rolling < 0
   or revenue_7d_rolling < 0
   or avg_duration_min < 0
   or avg_speed_mph < 0
