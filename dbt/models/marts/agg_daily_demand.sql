{{ config(materialized='table') }}

-- Demanda diária por zona de embarque. Grão: dia × zona.
-- Responde "como a demanda varia por hora do dia e dia da semana, por zona?" quando
-- consumida junto do horário; aqui fica o agregado diário que alimenta o gráfico.
--
-- Filtro: apenas is_valid_trip (exclui fora do período, distância zero, corridas
-- acima de 6 h e velocidade acima de 60 mph). O volume excluído é documentado no README.

with daily as (

    select
        pickup_at::date            as trip_date,
        pickup_zone_id             as zone_id,
        pickup_zone,
        pickup_borough,
        is_airport_trip,
        count(*)                   as trips,
        sum(total_amount)          as revenue,
        avg(total_amount)          as avg_ticket,
        avg(trip_distance)         as avg_distance_miles,
        avg(trip_duration_min)     as avg_duration_min,
        avg(speed_mph)             as avg_speed_mph
    from {{ ref('fct_trips') }}
    where is_valid_trip
    group by 1, 2, 3, 4, 5

)

select
    trip_date,
    zone_id,
    pickup_zone,
    pickup_borough,
    is_airport_trip,
    trips,
    round(revenue::numeric, 2)          as revenue,
    round(avg_ticket::numeric, 2)       as avg_ticket,
    round(avg_distance_miles::numeric, 2) as avg_distance_miles,
    round(avg_duration_min::numeric, 2) as avg_duration_min,
    round(avg_speed_mph::numeric, 2)    as avg_speed_mph
from daily
