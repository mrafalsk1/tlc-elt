{{ config(
    materialized='incremental',
    unique_key='trip_id',
    incremental_strategy='delete+insert',
    on_schema_change='fail'
) }}

-- Fato no grão de uma corrida. Carrega todas as linhas do intermediate (nenhuma é
-- descartada): a seleção do que é válido fica na flag is_valid_trip, e as agregações
-- em marts filtram por ela. Isso mantém a reconciliação com stg_yellow_trips exata.
--
-- trip_id é um hash determinístico da chave natural: a fonte não tem ID de corrida,
-- e um `row_number()` mudaria de valor a cada reload.
--
-- Incremental por mês: quando rodado com --vars '{"month": "2024-01"}', reprocessa
-- só aquele mês. delete+insert com unique_key garante idempotência (rodar 2x não
-- duplica) sem depender de índice único na origem.

with enriched as (

    select * from {{ ref('int_trips_enriched') }}

    {% if is_incremental() and var('month', none) is not none %}
    where pickup_at >= '{{ var("month") }}-01'::timestamp
      and pickup_at < ('{{ var("month") }}-01'::timestamp + interval '1 month')
    {% endif %}

)

select
    md5(
        concat_ws(
            '|',
            vendor_id::text,
            pickup_at::text,
            dropoff_at::text,
            total_amount::text
        )
    ) as trip_id,
    *
from enriched
