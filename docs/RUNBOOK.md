# Runbook — DAG `elt_tlc`

Operação local do pipeline ELT mensal (táxi de NYC). Roda todo dia 1º às 06:00
(America/Sao_Paulo), `catchup=False`, `max_active_runs=1`.

Ordem das tasks: `dbt_source_freshness` → `ingest_raw` → `dbt_build`.

## Retries, timeouts e SLA

| Task | `execution_timeout` | SLA inicial | Retries |
|---|---|---|---|
| `dbt_source_freshness` | 10 min | 15 min | 2, backoff exponencial (teto 30 min) |
| `ingest_raw` | 30 min | 45 min | 2, backoff exponencial (teto 30 min) |
| `dbt_build` | 60 min | 90 min | 2, backoff exponencial (teto 30 min) |

- O SLA inicial é `execution_timeout` + 50 %. **É provisório.** Os valores de p95
  ainda não foram medidos; ajustar após 3 runs reais.
- p95 medido (preencher após 3 runs): `dbt_source_freshness` medir · `ingest_raw` medir · `dbt_build` medir.

## (a) Onde ver logs

- Interface: http://localhost:8080 → DAG `elt_tlc` → run → task → **Log**.
- Terminal: `make logs` (segue o log do container `airflow`).
- Log de uma task específica: `docker compose exec airflow airflow tasks logs elt_tlc <task_id> <run_id>` (ou pela UI).

## (b) Falha no ingest (`ingest_raw`)

1. Ver o erro no log da task. Causas comuns: download do Parquet do mês indisponível,
   arquivo corrompido, timeout de 30 min.
2. Conferir `data/alerts/alerts.jsonl` (ver seção g): o alerta `task_failure` traz o `try_number`.
3. Se for falha transitória, o retry automático (2x, backoff) pode resolver sozinho.
4. Se não resolver: corrigir a causa e limpar a task na UI (**Clear**). Como a ingestão
   é idempotente por `_source_file`, limpar e reexecutar não duplica dados.

## (c) Falha no dbt (`dbt_build`)

1. Ver no log qual modelo/teste falhou (`Failure in test ...` ou `Database Error in model ...`).
2. Reproduzir localmente: `make dbt` (ou `make test-dbt` para só os testes).
3. Corrigir o modelo ou o dado de origem e limpar a task `dbt_build` na UI.
4. Não marcar a task como sucesso sem o `dbt build` ter passado.

## (d) SLA miss

- Gera linha `type: sla_miss`, `severity: warning` no `alerts.jsonl`, uma por task atrasada.
- SLA miss **não** cancela a task: ela continua rodando. Verificar se terminou com sucesso.
- Se o atraso for recorrente, medir o p95 de 3 runs e ajustar o SLA em `dags/elt_tlc.py`,
  registrando o valor novo aqui na tabela.

## (e) Alerta de qualidade (lacuna 3)

Ainda não implementado. Quando existir (Great Expectations + alerta), a falha de
checagem vai para o mesmo `alerts.jsonl` com `type` próprio e este item será
atualizado com o procedimento.

## (f) Reprocessar 1 mês sem duplicar

1. Na UI, abrir o run do mês desejado (ou disparar um run manual com a data do mês).
2. Limpar (**Clear**) as tasks `ingest_raw` e `dbt_build` daquele run.
3. Ou pela linha de comando, dentro do container:
   `docker compose exec airflow airflow dags trigger elt_tlc --logical-date 2024-02-01T06:00:00`
   (ajustar a data para o mês desejado).

Por que não duplica: `ingest.py` faz DELETE + INSERT por `_source_file` (D-05), e
`fct_trips` é delete+insert com `unique_key = trip_id` (D-03).

## (g) `alerts.jsonl`: onde fica e como ler

- Caminho: `data/alerts/alerts.jsonl` no host (no container: `/opt/airflow/data/alerts/alerts.jsonl`).
  Pode ser trocado pela variável `ALERTS_FILE`.
- Formato: uma linha JSON por alerta (JSONL, append-only). Campos:
  `ts`, `source`, `type`, `severity`, `dag_id`, `task_id`, `run_id`, `logical_date`, `message`, `details`.
- Tipos: `task_failure` (critical) e `sla_miss` (warning).
- Webhook opcional: se `ALERT_WEBHOOK_URL` estiver definida, o mesmo JSON é enviado por POST
  (timeout 5 s). Falha no webhook é logada e não interrompe o DAG; o JSONL continua sendo a fonte.

Ler os últimos alertas:

```bash
tail -n 20 data/alerts/alerts.jsonl
```

Filtrar só falhas críticas (requer `jq`):

```bash
jq -c 'select(.severity == "critical")' data/alerts/alerts.jsonl
```
