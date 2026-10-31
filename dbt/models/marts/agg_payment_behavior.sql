{{ config(materialized='table') }}

-- Comportamento de gorjeta por forma de pagamento. Grão: método × faixa de gorjeta.
-- Responde a pergunta clássica: cartão dá mais gorjeta que dinheiro? (Sim — e o
-- número é o gancho do gráfico no README.)
--
-- O denominador é fare_amount, não total_amount: taxas e pedágios não recebem gorjeta,
-- então dividir pelo total subestimaria a generosidade do passageiro.

with base as (

    select
        case payment_type
            when 1 then 'credit_card'
            when 2 then 'cash'
            when 3 then 'no_charge'
            when 4 then 'dispute'
            when 5 then 'unknown'
            when 6 then 'voided_trip'
            else 'other'
        end as payment_method,
        case
            when tip_pct is null then 'sem_base'
            when tip_pct = 0    then '0%'
            when tip_pct <= 0.10 then '(0, 10%]'
            when tip_pct <= 0.20 then '(10, 20%]'
            when tip_pct <= 0.30 then '(20, 30%]'
            else '> 30%'
        end as tip_bucket,
        tip_pct,
        tip_amount,
        total_amount,
        fare_amount
    from {{ ref('fct_trips') }}
    where is_valid_trip

)

select
    payment_method,
    tip_bucket,
    count(*)                            as trips,
    round(avg(tip_pct)::numeric, 4)     as avg_tip_pct,
    round(sum(tip_amount)::numeric, 2)  as total_tips,
    round(avg(total_amount)::numeric, 2) as avg_ticket,
    round(sum(fare_amount)::numeric, 2) as total_fare
from base
group by 1, 2
order by 1, 2
