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

Legenda de status: pendente | em_andamento | validada | bloqueada

## Evidências

| Data | Escopo | Comando | Resultado |
|------|--------|---------|-----------|
| 2026-11-07 | Validação completa local (Python 3.11 + Postgres 16) | `CI=true make validate` | check_env OK, ruff All checks passed, pytest 7 passed, dbt build 43/43 PASS (0 erro) |
| 2026-11-07 | Documentação dbt | `dbt docs generate --profiles-dir . --target ci` | catalog.json gerado |
| 2026-11-07 | CI do GitHub Actions (run #7, commit `5fd5ce9`) | push em `main` | workflow `validate` concluído com sucesso (https://github.com/mrafalsk1/tlc-elt/actions/runs/42365555135) |
| 2026-11-07 | F-01/F-02/F-08: idempotência e gráficos (Python 3.11 + Postgres 16 limpo) | `make validate` | ruff All checks passed, pytest 15 passed (4 de integração), dbt build 43/43 PASS (0 erro) |
