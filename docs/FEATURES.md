# Features — Projeto A (ELT NYC TLC)

| ID | Feature | Critério de aceite | Teste que a cobre | Status |
|----|---------|-------------------|-------------------|--------|
| F-01 | Ingestão de Parquet NYC TLC (ingest.py) | Baixa 3 meses + lookup de zonas; idempotente por _source_file | tests/unit/test_ingest.py (URL + normalização) + tests/integration/test_ingest_db.py (idempotência por arquivo) | validada |
| F-02 | Carga de taxi_zones (load_zones.py) | Truncate+insert; 265 linhas; valida colunas esperadas | tests/unit/test_load_zones.py (colunas + URL) + tests/integration/test_load_zones_db.py (265 linhas, truncate+insert) | validada |
| F-03 | dbt staging (stg_yellow_trips, stg_taxi_zones) | Filtros de sanidade, dedup, testes not_null/accepted_values | `dbt build` (testes de staging) | validada |
| F-04 | dbt intermediate (int_trips_enriched) | Nenhuma linha descartada; flags de qualidade | `dbt build` (testes de intermediate) | validada |
| F-05 | dbt marts (fct_trips, dim_zones, agg_daily_demand, agg_payment_behavior) | trip_id único, relacionamentos, is_valid_trip | `dbt build` (testes de marts) | validada |
| F-06 | Teste de reconciliação receita staging ↔ marts | Retorna 0 linhas quando receitas batem | dbt/tests/assert_revenue_reconciliation.sql | validada |
| F-07 | CI do GitHub Actions (ruff + dbt build) | `make validate` passa no push | .github/workflows/ci.yml | validada |
| F-08 | Geração de gráficos (gerar_graficos.py) | 3 PNGs em data/graficos/, textos em inglês | tests/unit/test_graficos.py (3 PNGs válidos, nomes e queries) | validada |
| F-09 | Modulo Terraform (S3 + RDS + Glue + IAM) | `fmt -check` e `validate` passam; nenhum recurso aplicado | job `terraform` do CI + `make tf-validate` | validada |
| F-10 | Alertas locais (JSONL + webhook opcional) | Toda falha/SLA de DagRun vira 1 linha JSONL; webhook ausente não quebra nada | tests/unit/test_alerting.py (16 testes) | validada |
| F-11 | Operação do DAG | retries 2 com backoff 5→30 min; execution_timeout 10/30/60 min; dagrun_timeout 3 h; callbacks de task e de DagRun | tests/unit/test_dag_contract.py + docs/RUNBOOK.md | validada |
| F-12 | Qualidade com Great Expectations 1.25.0 | 11 expectativas (críticas e avisos), exit 1 se critical falha, alerta local; paridade rules↔GX | tests/unit/test_expectations.py + test_quality_parity.py + `make quality` | validada |
| F-13 | Dagster comparativo | 2 assets + schedule mensal; `definitions validate` e materialização | `make dagster-check` + `.github/workflows/dagster-ci.yml` | validada |
| F-14 | Features diárias por zona (ML) | grão `(zone_id, trip_date)` único; janelas 7d e lag 1d | `dbt build` + assert_features_daily_zone_unique/non_negative | validada |
| F-15 | Features de grafo de zonas | 262 zonas e 37.255 arestas; pagerank + betweenness por zona | tests/unit/test_graph_features.py + assert_features_zone_graph_ranges.sql | validada |

Legenda de status: pendente | em_andamento | validada | bloqueada

## Evidências

| Data | Escopo | Comando | Resultado |
|------|--------|---------|-----------|
| 2026-11-07 | Validação completa local (Python 3.11 + Postgres 16) | `CI=true make validate` | check_env OK, ruff All checks passed, pytest 7 passed, dbt build 43/43 PASS (0 erro) |
| 2026-11-07 | Documentação dbt | `dbt docs generate --profiles-dir . --target ci` | catalog.json gerado |
| 2026-11-07 | CI do GitHub Actions (run #7, commit `5fd5ce9`) | push em `main` | workflow `validate` concluído com sucesso (https://github.com/mrafalsk1/tlc-elt/actions/runs/42365555135) |
| 2026-11-07 | F-01/F-02/F-08: idempotência e gráficos (Python 3.11 + Postgres 16 limpo) | `make validate` | ruff All checks passed, pytest 15 passed (4 de integração), dbt build 43/43 PASS (0 erro) |
| 2026-11-07 | CI do GitHub Actions (run #8, commit `ebe2ac1`) | push em `main` | workflow `build` concluído com sucesso (https://github.com/mrafalsk1/tlc-elt/actions/runs/42373813404) |
| 2026-11-07 | Critérios §8: idempotência do DAG e demo de dado sujo | replay de 3 meses + `dbt test` com linha suja | raw 9.554.778→9.554.778, fct_trips 9.412.455→9.412.455, 0 `trip_id` duplicados; `accepted_values` falha com `payment_type=99` |
| 2026-11-17 | Terraform 1.9.8 / provider aws 5.100.0 | `terraform init -backend=false && terraform fmt -check -recursive && terraform validate` | fmt OK; "Success! The configuration is valid." |
| 2026-11-24 | Lacuna 5: alertas e operação do DAG (`6ebee9e`, `f85bb79`, `ff53501`) | `make validate` + `pytest tests/unit` + `airflow dags list-import-errors` | validate OK (37 passed, dbt 43/43); 15 testes de alerta/contrato; DAG parseado com dagrun_timeout 3 h e callbacks |
| 2026-11-24 | Lacuna 3: Great Expectations sobre fixture e sobre jan/2024 (`7646351`, `9828bd1`) | `make quality` (fixture) + run real no Parquet | fixture: 7 expectativas falham, exit 1; real (2.964.624 linhas): fare_between 37.494, dropoff_after_pickup 870, distance_between 31, demais 0; paridade rules↔GX 1 passed |
| 2026-11-24 | Lacuna 8: Dagster 1.13.31 (`8a1a2d2`) | `make dagster-check` + `dagster asset materialize --select 'raw_trips+'` | validate e asset list OK; 35 dias, 2.964.624 viagens, receita 79.456.384,28 em DuckDB |
| 2026-11-24 | Lacuna 9: features e grafo (`3cb4205`, `69289fa`) | `dbt build --target ci` + `python scripts/build_knowledge_graph.py` | dbt PASS=58; features 20.338 linhas/261 zonas (jan–mar/2024); grafo 262 zonas/37.255 arestas/9.554.778 viagens/2,7 s |
| 2026-11-24 | CI do GitHub Actions (run #19, commit `faffeca`) | push em `main` | jobs `build` e `terraform` verdes; job `Dagster` (run #1) verde (https://github.com/mrafalsk1/tlc-elt/actions/runs/45327445158) |
