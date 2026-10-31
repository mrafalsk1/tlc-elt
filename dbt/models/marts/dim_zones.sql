{{ config(materialized='table') }}

-- Dimensão de zonas pronta para consumo: o mesmo lookup da staging, com a marca
-- de aeroporto que as agregações e o dashboard usam para separar corridas de aeroporto.

select
    zone_id,
    borough,
    zone,
    service_zone,
    (zone in ('JFK Airport', 'LaGuardia Airport', 'Newark Airport')) as is_airport
from {{ ref('stg_taxi_zones') }}
