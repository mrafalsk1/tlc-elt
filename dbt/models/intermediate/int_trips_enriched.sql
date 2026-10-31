{{ config(materialized='view') }}

-- Intermediate: uma linha por corrida, já com nomes de zona e flags de negócio.
--
-- Decisão importante: este modelo NÃO descarta linhas. Tudo o que é outlier vira
-- flag, e quem decide excluir é o consumidor (as agregações em marts). Duas razões:
--   1. O teste assert_revenue_reconciliation compara receita de fct_trips com
--      stg_yellow_trips; qualquer filtro aqui quebraria a reconciliação entre camadas.
--   2. Outlier é contexto, não erro: a taxa de corridas com distância zero é um
--      resultado do projeto, não algo para esconder.
--
-- Flags:
--   is_out_of_period  -> a corrida não cai no mês do arquivo de origem (timestamps
--                        de 2002/2008/2009 aparecem nos arquivos de 2024)
--   has_zero_distance -> taxímetro registrou distância 0 (≈2% da base)
--   is_long_trip      -> duração acima de 6 h
--   is_fast_trip      -> velocidade média acima de 60 mph
--   is_airport_trip   -> embarque em JFK, LaGuardia ou Newark
--   is_night_trip     -> embarque entre 22h e 6h
--   is_valid_trip     -> nenhuma das quatro condições de exclusão acima

with trips as (

    select * from {{ ref('stg_yellow_trips') }}

),

zones as (

    select * from {{ ref('stg_taxi_zones') }}

),

joined as (

    select
        t.*,
        zp.borough as pickup_borough,
        zp.zone    as pickup_zone,
        zd.borough as dropoff_borough,
        zd.zone    as dropoff_zone,
        (zp.zone in ('JFK Airport', 'LaGuardia Airport', 'Newark Airport')) as is_airport_trip,
        (
            extract(hour from t.pickup_at) >= 22
            or extract(hour from t.pickup_at) < 6
        ) as is_night_trip
    from trips t
    left join zones zp on t.pickup_zone_id = zp.zone_id
    left join zones zd on t.dropoff_zone_id = zd.zone_id

),

flagged as (

    select
        *,
        -- Mês esperado, derivado do nome do arquivo de origem (…_2024-01.parquet).
        -- Assim o flag continua correto se o backfill cobrir outros meses.
        to_date(substring(_source_file from '(\d{4}-\d{2})') || '-01', 'YYYY-MM-DD') as source_month,
        (trip_distance = 0)                                                as has_zero_distance,
        (trip_duration_min > 360)                                          as is_long_trip,
        (speed_mph > 60)                                                   as is_fast_trip
    from joined

)

select
    *,
    (date_trunc('month', pickup_at)::date <> source_month)              as is_out_of_period,
    not (
        date_trunc('month', pickup_at)::date <> source_month
        or trip_distance = 0
        or trip_duration_min > 360
        or speed_mph > 60
    )                                                                   as is_valid_trip
from flagged
