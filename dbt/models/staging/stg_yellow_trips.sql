{{ config(materialized='view') }}

-- Staging: renomear, tipar, descartar registros inválidos e deduplicar.
--
-- Regras de negócio (todas documentadas aqui e testadas em _models.yml):
--   1. fare_amount > 0        -> corrida com tarifa zero ou negativa é erro de medidor,
--                                não desconto. Sem esse filtro, ticket médio e receita mentem.
--   2. trip_distance >= 0     -> distância negativa é impossível fisicamente.
--   3. dropoff_at > pickup_at -> corrida que termina antes de começar (ou com duração zero)
--                                quebra qualquer cálculo de velocidade.
--   4. Deduplicação pela chave natural (vendor + pickup + dropoff + total_amount):
--      a fonte não tem ID de corrida, então duas linhas idênticas nesses quatro campos
--      são o mesmo registro. Mantemos a de `_loaded_at` mais recente.
--
-- Fora do escopo daqui (de propósito):
--   - duração > 6 h, velocidades absurdas e zonas inválidas são outliers de negócio,
--     tratados em intermediate/int_trips_enriched, onde a regra fica visível junto do join.
--   - trip_id determinístico nasce em marts/fct_trips, junto com o grão da tabela fato.

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
        ratecodeid                          as rate_code_id,
        store_and_fwd_flag,
        pulocationid                        as pickup_zone_id,
        dolocationid                        as dropoff_zone_id,
        payment_type,
        fare_amount,
        extra,
        mta_tax,
        tip_amount,
        tolls_amount,
        improvement_surcharge,
        congestion_surcharge,
        airport_fee,
        total_amount,
        _source_file,
        _loaded_at

    from source

),

filtered as (

    select *
    from renamed
    where fare_amount > 0
      and trip_distance >= 0
      and dropoff_at > pickup_at

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by vendor_id, pickup_at, dropoff_at, total_amount
            order by _loaded_at desc
        ) as _row_number
    from filtered

),

enriched as (

    select
        *,
        -- Duração em minutos: base para velocidade e para o filtro de outliers.
        -- O cast para numeric é obrigatório: no Postgres não existe round(double, int).
        round(
            (extract(epoch from (dropoff_at - pickup_at)) / 60.0)::numeric,
            2
        ) as trip_duration_min,
        -- nullif evita divisão por zero em corridas com duração ~0.
        round(
            (
                trip_distance
                / nullif(extract(epoch from (dropoff_at - pickup_at)) / 3600.0, 0)
            )::numeric,
            2
        ) as speed_mph,
        -- Gorjeta como fração da tarifa (não do total: taxas não recebem gorjeta).
        round((tip_amount / nullif(fare_amount, 0))::numeric, 4) as tip_pct

    from deduplicated
    where _row_number = 1

)

select
    vendor_id,
    pickup_at,
    dropoff_at,
    passenger_count,
    trip_distance,
    rate_code_id,
    store_and_fwd_flag,
    pickup_zone_id,
    dropoff_zone_id,
    payment_type,
    fare_amount,
    extra,
    mta_tax,
    tip_amount,
    tolls_amount,
    improvement_surcharge,
    congestion_surcharge,
    airport_fee,
    total_amount,
    trip_duration_min,
    speed_mph,
    tip_pct,
    _source_file,
    _loaded_at
from enriched
