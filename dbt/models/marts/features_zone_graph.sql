{{ config(materialized='table') }}

-- Features de centralidade do grafo de zonas (pickup → dropoff), no grão de zona.
-- O seed é gerado por scripts/build_knowledge_graph.py a partir do Parquet cru
-- (262 zonas, 37.255 arestas, 9.554.778 viagens em jan–mar/2024).
--
-- LEFT JOIN a partir de dim_zones de propósito: toda zona da dimensão aparece,
-- e zona sem aresta recebe 0 em vez de desaparecer. No CI (warehouse vazio) o
-- modelo devolve 0 linhas e os testes continuam válidos.

select
    z.zone_id,
    z.borough,
    z.zone,
    z.is_airport,
    coalesce(g.in_degree, 0)              as in_degree,
    coalesce(g.out_degree, 0)             as out_degree,
    coalesce(g.weighted_in_trips, 0)      as weighted_in_trips,
    coalesce(g.weighted_out_trips, 0)     as weighted_out_trips,
    coalesce(g.pagerank, 0)               as pagerank,
    coalesce(g.betweenness_centrality, 0) as betweenness_centrality
from {{ ref('dim_zones') }} z
left join {{ ref('zone_graph_features') }} g on g.zone_id = z.zone_id
