-- Teste singular: centralidades e graus ficam nas faixas esperadas.
-- pagerank soma ~1 no grafo inteiro, então cada nó fica em [0, 1];
-- betweenness é normalizada; pesos e graus não podem ser negativos.
select *
from {{ ref('features_zone_graph') }}
where pagerank < 0
   or pagerank > 1
   or betweenness_centrality < 0
   or betweenness_centrality > 1
   or in_degree < 0
   or out_degree < 0
   or weighted_in_trips < 0
   or weighted_out_trips < 0
