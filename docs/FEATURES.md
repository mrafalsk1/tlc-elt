# Features — Projeto A (ELT NYC TLC)

| ID | Feature | Critério de aceite | Teste que a cobre | Status |
|----|---------|-------------------|-------------------|--------|
| F-01 | Ingestão de Parquet NYC TLC (ingest.py) | Baixa 3 meses + lookup de zonas; idempotente por _source_file | scripts/tests/unit/test_ingest_idempotency.py | pendente |
| F-02 | Carga de taxi_zones (load_zones.py) | Truncate+insert; 265 linhas; valida colunas esperadas | scripts/tests/unit/test_load_zones_schema.py | pendente |
| F-03 | dbt staging (stg_yellow_trips, stg_taxi_zones) | Filtros de sanidade, dedup, testes not_null/accepted_values | dbt tests (staging) | pendente |
| F-04 | dbt intermediate (int_trips_enriched) | Nenhuma linha descartada; flags de qualidade | dbt tests (intermediate) | pendente |
| F-05 | dbt marts (fct_trips, dim_zones, agg_daily_demand, agg_payment_behavior) | trip_id único, relacionamentos, is_valid_trip | dbt tests (marts) | pendente |
| F-06 | Teste de reconciliação receita staging ↔ marts | Retorna 0 linhas quando receitas batem | dbt/tests/assert_revenue_reconciliation.sql | pendente |
| F-07 | CI do GitHub Actions (ruff + dbt build) | `make validate` passa no push | .github/workflows/ci.yml | pendente |
| F-08 | Geração de gráficos (gerar_graficos.py) | 3 PNGs em data/graficos/, textos em inglês | scripts/tests/unit/test_graficos_saida.py | pendente |

Legenda de status: pendente | em_andamento | validada | bloqueada
