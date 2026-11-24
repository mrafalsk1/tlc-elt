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
- Motivo: separa transformação (dbt) de visualização (matplotlib); o CI valida a geração dos 3 PNGs com uma conexão falsa (tests/unit/test_graficos.py), sem precisar de dados carregados.
- matplotlib==3.11.2 fixado em requirements.txt (antes só existia no container, o que quebrava o CI).

## D-08: Carga do lookup de zonas com truncate+insert
- load_zones.py usa TRUNCATE + INSERT, não `if_exists="replace"`.
- Motivo: mantém a estrutura da tabela (tipos, PK, índices, grants) e continua idempotente; o `replace` derrubava e recriava a tabela a cada carga.

## D-09: Terraform validado, nao aplicado
- `infra/terraform/` descreve o mesmo pipeline na AWS: bucket S3 da camada raw, RDS Postgres 16 como warehouse, Glue catalog + crawler sobre o prefixo `raw/` e a role de IAM dos dois.
- So `terraform fmt -check` + `terraform validate` rodam (job `terraform` do CI, sem credencial e sem state remoto). Nenhum recurso e criado.
- Motivo: o objetivo e demonstrar IaC com revisao e portao de CI, nao hospedar o projeto. Rodar continua sendo `docker compose` (D-06); aplicar custaria ~US$ 15-20/mes de RDS.
- A senha do RDS usa `manage_master_user_password` (Secrets Manager), entao nao existe segredo em codigo nem em `terraform.tfvars`.

## D-10: Controle de atraso sem sla do Airflow (dagrun_timeout + execution_timeout)
- O DAG elt_tlc nao usa sla nem sla_miss_callback.
- Motivo: no Airflow 2.x o SLA e contado a partir do logical_date. Num DAG mensal (0 6 1 * *) o run so dispara no fim do intervalo, entao o logical_date fica ~31 dias no passado e qualquer SLA curto dispara em todo run (alerta vira ruido).
- Controle adotado: execution_timeout por task (10/30/60 min) + dagrun_timeout do DAG (3 h).
- Alertas: falha de task vai para alerting.alert_failure (on_failure_callback de task). Run morto por dagrun_timeout vai para alerting.alert_dagrun_failure (on_failure_callback do DAG, contexto de DagRun; confirmado no scheduler do Airflow 2.10.5, que cria o callback com msg="timed_out"). dagrun_timeout NAO dispara o callback de task.
- dagrun_timeout de 3 h e um teto deliberado, menor que o pior caso teorico (345 min com retries completos): evita que um run travado ocupe o slot mensal por dias. Estouro em run normal = investigar, nao aumentar o teto sem medir.
- Revisitar se o DAG passar a ser diario/horario: ai sla volta a ter sentido.

## D-11: Qualidade com Great Expectations 1.x, em venv separado
- Regras em Pandas puro (scripts/quality/rules.py, testadas sem GX); o GX so roda em scripts/quality/gx_runner.py, unico modulo que importa great_expectations.
- Versao: great-expectations==1.25.0 (fluent API), freeze em requirements-quality.txt, venv .venv-quality (Python 3.12). Nao entra em requirements.txt.
- Motivo: validate e CI nao podem depender de GX (peso e instalacao); a checagem de qualidade e um passo a parte do ELT. A fluent API 1.x funcionou, entao nao foi preciso descer para 0.18.19.
- Regras sobre o schema cru (nomes do Parquet). O dbt normaliza depois.
- payment_type aceita 0-6 (contrato do dbt), nao 1-6 como o plano sugeria.
- Nao roda sobre os 9,5 M no CI: run manual, contagens registradas em DATA_CONTRACTS.md secao 10.
- Paridade: tests/unit/test_quality_parity.py roda as duas implementacoes sobre a fixture e compara as contagens por expectativa (pulado sem GX). Foi ele que mostrou que a FK nula divergia: `rules.py` contava o NaN como violacao e o `ExpectColumnValuesToBeInSet` do GX ignorava. Correcao: `pickup_zone_not_null`/`dropoff_zone_not_null` reportam o nulo e a FK ignora nulo nos dois motores.
- `dropoff_after_pickup` e regra composta (duas colunas): nao tem expectativa GX equivalente, entao e avaliada em `rules.py` e o runner usa a mesma funcao como complemento. Nao e fachada, e a unica regra que o GX nao cobre.

## D-12: Dagster como comparativo, em venv separado
- `dagster_project/definitions.py`: 2 assets (`raw_trips` le o Parquet cru; `daily_agg` agrega viagens e receita por dia em DuckDB) + schedule mensal `monthly_tlc_refresh`, no mesmo calendario do DAG de Airflow.
- Motivo: a lacuna 8 pede um segundo orquestrador. O objetivo e saber comparar, nao migrar: dbt e Airflow continuam sendo o pipeline real.
- O diretorio NAO se chama `dagster/` de proposito: um pacote local com esse nome sombrearia a lib `dagster` no import.
- Airflow vs Dagster, na pratica deste projeto:
  - Airflow organiza por **task** e agenda por tempo; o lineage entre etapas so existe se voce declarar XCom/dependencias.
  - Dagster organiza por **asset** (o dado e o contrato): `daily_agg` declara `raw_trips` como entrada, entao a dependencia e o proprio lineage. `dagster asset materialize --select 'raw_trips+'` rematerializa a linhagem inteira.
  - Dagster exige IO manager para persistir saida entre assets (aqui: fs padrao para o DataFrame e DuckDB para a tabela); Airflow nao persiste nada por padrao, cada task se vira.
  - Custo: Dagster e um framework maior (grpc, webserver, storage) para o mesmo fluxo; Airflow ja esta no compose e o dbt roda igual.
  - Quando escolher: Dagster quando o ativo (tabela/modelo) e o centro e o time quer lineage/particoes de primeira classe; Airflow quando o ecossistema de operadores prontos e a familiaridade pesam mais (caso deste projeto).
- Versoes: dagster==1.13.31, dagster-duckdb==0.29.31, duckdb==2.0.1 (requirements-dagster.txt). Validado em 2026-11-24: `definitions validate`, `asset list` e materializacao de `raw_trips+` (35 dias, 2.964.624 viagens, receita 79.456.384,28).
- O job de CI e opcional (paths filter) para nao engordar o build principal; `make validate` nao mudou.
