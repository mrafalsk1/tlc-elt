#!/usr/bin/env python3
"""DAG: ELT mensal dos dados de táxi de NYC.

Executa, todo dia 1º às 06:00:
  1. dbt source freshness (verifica se o raw chegou)
  2. ingest_raw: baixa o Parquet do mês e carrega em raw (idempotente por _source_file)
  3. dbt_build: roda staging → intermediate → marts com --vars month (incremental, idempotente)

Rodar o mesmo mês duas vezes não duplica dados:
  - ingest.py faz DELETE + INSERT por _source_file
  - fct_trips é delete+insert com unique_key = trip_id (hash da chave natural)

Alertas: falha de task vai para alerting.alert_failure (via default_args).
Grava em data/alerts/alerts.jsonl. Controle de atraso: execution_timeout por
task + dagrun_timeout no DAG (sla não é usado; ver docs/DECISIONS.md D-10).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pendulum
from airflow.decorators import dag
from airflow.operators.bash import BashOperator

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import alerting

DBT_DIR = "/opt/airflow/dbt"

MONTH = "{{ (data_interval_start).strftime('%Y-%m') }}"

@dag(
    dag_id="elt_tlc",
    description="Ingestão + transformação (dbt) dos dados de táxi de NYC",
    schedule="0 6 1 * *",  # todo dia 1º, 06:00
    start_date=pendulum.datetime(2024, 1, 1, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=pendulum.duration(hours=3),
    default_args={
        "retries": 2,
        "retry_delay": pendulum.duration(minutes=5),
        "retry_exponential_backoff": True,
        "max_retry_delay": pendulum.duration(minutes=30),
        "on_failure_callback": alerting.alert_failure,
    },
    tags=["elt", "tlc"],
)
def elt_tlc():
    freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=(
            f"cd {DBT_DIR} && "
            f"dbt source freshness --profiles-dir ."
        ),
        execution_timeout=pendulum.duration(minutes=10),
    )

    ingest = BashOperator(
        task_id="ingest_raw",
        bash_command=f"python /opt/airflow/scripts/ingest.py --months {MONTH}",
        execution_timeout=pendulum.duration(minutes=30),
    )

    transform = BashOperator(
        task_id="dbt_build",
        bash_command=(
            f"cd {DBT_DIR} && "
            f"dbt build --profiles-dir . --vars '{{\"month\": \"{MONTH}\"}}'"
        ),
        execution_timeout=pendulum.duration(minutes=60),
    )

    freshness >> ingest >> transform


elt_tlc()
