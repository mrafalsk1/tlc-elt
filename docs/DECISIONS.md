# Decisões técnicas — Projeto A

## D-01: Armazenamento de dados
- Banco: Postgres 16 (via docker-compose local; serviço Postgres no CI).
- Schema separado: `raw` (cópia fiel da fonte), `staging` (views), `intermediate` (views), `marts` (tabelas).
- Motivo: separa camada de bronze (raw), transformação lógica (staging/intermediate) e consumo (marts).

## D-02: dbt como engine de transformação
- dbt-core 1.8.2 + dbt-postgres 1.8.2.
- Modelos staging e intermediate são views; marts são tabelas (fato e agregações).
- Motivo: views evitam custo de armazenamento para camadas intermediárias; tabelas em marts otimizam leitura de agregações.

## D-03: Chave de deduplicação (trip_id)
- `trip_id = md5(vendor_id | pickup_at | dropoff_at | total_amount)` em marts/fct_trips.
- Motivo: a fonte NYC TLC não tem ID de corrida; um hash determinístico da chave natural permite delete+insert idempotente sem índice único na origem.

## D-04: Nenhuma linha descartada no intermediate
- int_trips_enriched mantém todas as linhas; outliers viram flags (is_out_of_period, has_zero_distance, is_long_trip, is_fast_trip).
- Motivo: o teste assert_revenue_reconciliation compara receita de staging e marts; qualquer filtro quebraria a reconciliação. As agregações em marts filtram por is_valid_trip.

## D-05: Ingestão idempotente
- ingest.py faz DELETE + INSERT por _source_file antes de carregar cada Parquet.
- Motivo: backfill ou reexecução do mesmo mês não duplica dados.

## D-06: CI sem deploy
- O CI roda no GitHub Actions apenas para validar (ruff + dbt build + dbt docs generate).
- Não há deploy para Render, Railway, VPS, AWS, etc.
- Motivo: projeto é de portfólio; o CI serve como prova de que o pipeline é válido.

## D-07: Geração de gráficos separada do dbt
- gerar_graficos.py lê de marts e salva PNGs em data/graficos/.
- Motivo: separa transformação (dbt) de visualização (matplotlib); o CI valida que os gráficos existem no README.
