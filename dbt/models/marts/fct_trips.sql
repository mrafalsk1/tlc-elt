{{ config(
    materialized='incremental',
    unique_key='trip_id',
    incremental_strategy='delete+insert'
) }}

-- Fato no grão de uma corrida.
-- TODO(semana 3):
--   1. Gerar trip_id determinístico (hash da chave natural)
--   2. Incremental por mês: filtrar por var('month') quando is_incremental()
--   3. Testar idempotência: rodar o mesmo mês 2x e comparar contagens

with trips as (

    select * from {{ ref('stg_yellow_trips') }}

    {% if is_incremental() %}
    -- and pickup_at >= '{{ var("month") }}-01'
    {% endif %}

)

select
    -- md5(concat_ws('|', vendor_id, pickup_at, dropoff_at, total_amount)) as trip_id,
    *
from trips
