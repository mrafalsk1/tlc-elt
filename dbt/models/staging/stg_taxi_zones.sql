{{ config(materialized='view') }}

-- Dimensão de zonas da TLC (265 linhas). A fonte já vem limpa, com duas exceções
-- reais: a LocationID 264 vem com Borough "Unknown" e Zone vazia, e a 265 vem com
-- Borough vazio e Zone "Outside of NYC". Normalizamos os vazios para um rótulo
-- explícito — assim `not_null` no modelo significa "nunca entrego célula vazia",
-- e não "a fonte é perfeita".
--
-- `stg_yellow_trips.pickup_zone_id` / `dropoff_zone_id` referenciam `zone_id`.

with source as (

    select * from {{ source('raw', 'taxi_zones') }}

),

renamed as (

    select
        locationid                                        as zone_id,
        coalesce(nullif(trim(borough), ''), 'Unknown')     as borough,
        coalesce(nullif(trim(zone), ''), 'Unknown')        as zone,
        coalesce(nullif(trim(service_zone), ''), 'N/A')    as service_zone
    from source

)

select * from renamed
