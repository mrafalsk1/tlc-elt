{{ config(materialized='table') }}

-- Features de ML no grão dia × zona de embarque (uma linha por zone_id + trip_date).
-- Fonte: agg_daily_demand, que já filtra is_valid_trip. As janelas de 7 dias
-- incluem o próprio dia (rows 6 preceding) e não atravessam zonas.

with daily as (

    select
        d.trip_date,
        d.zone_id,
        d.trips,
        d.revenue,
        d.avg_ticket,
        d.avg_duration_min,
        d.avg_speed_mph,
        z.is_airport
    from {{ ref('agg_daily_demand') }} d
    left join {{ ref('dim_zones') }} z on z.zone_id = d.zone_id

),

features as (

    select
        trip_date,
        zone_id,
        trips,
        revenue,
        avg_ticket,
        avg_duration_min,
        avg_speed_mph,
        coalesce(is_airport, false)              as is_airport_zone,
        sum(trips) over w7                       as trips_7d_rolling,
        round(sum(revenue) over w7, 2)           as revenue_7d_rolling,
        round(avg(trips) over w7, 2)             as trips_7d_avg,
        lag(trips) over (
            partition by zone_id order by trip_date
        )                                        as trips_prev_day
    from daily
    window w7 as (
        partition by zone_id
        order by trip_date
        rows between 6 preceding and current row
    )

)

select * from features
