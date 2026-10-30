{{ config(materialized='view') }}

-- Staging: renomear, tipar e descartar registros inválidos.
-- TODO(semana 2):
--   1. Filtrar fare_amount > 0, trip_distance >= 0, dropoff > pickup
--   2. Deduplicar pela chave natural (vendorid + pickup + dropoff + total_amount)
--   3. Criar trip_duration_min, speed_mph, tip_pct
--   4. Documentar cada regra de negócio em comentário

with source as (

    select * from {{ source('raw', 'yellow_trips') }}

),

renamed as (

    select
        vendorid                            as vendor_id,
        tpep_pickup_datetime                as pickup_at,
        tpep_dropoff_datetime               as dropoff_at,
        passenger_count,
        trip_distance,
        pulocationid                        as pickup_zone_id,
        dolocationid                        as dropoff_zone_id,
        payment_type,
        fare_amount,
        tip_amount,
        total_amount

    from source

),

filtered as (

    select *
    from renamed
    where 1 = 1
        -- and fare_amount > 0
        -- and trip_distance >= 0
        -- and dropoff_at > pickup_at

)

select * from filtered
