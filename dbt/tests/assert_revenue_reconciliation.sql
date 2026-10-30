-- Teste singular: a receita não pode "vazar" entre staging e marts.
-- Deve retornar 0 linhas. Qualquer linha retornada = falha.

with staging_total as (

    select
        sum(total_amount) as total,
        count(*)          as trips
    from {{ ref('stg_yellow_trips') }}

),

marts_total as (

    select
        sum(total_amount) as total,
        count(*)          as trips
    from {{ ref('fct_trips') }}

)

select
    s.total  as staging_revenue,
    m.total  as marts_revenue,
    s.trips  as staging_trips,
    m.trips  as marts_trips
from staging_total s
cross join marts_total m
where abs(coalesce(s.total, 0) - coalesce(m.total, 0)) > 0.01
   or s.trips <> m.trips
