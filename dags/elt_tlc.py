"""DAG: ELT mensal dos dados de táxi de NYC.

TODO(semana 4):
  1. Rodar 1 mês pelo DAG e conferir a UI.
  2. Parametrizar o mês ({{ ds_nodash }}[:6] vira YYYY-MM).
  3. Garantir idempotência: rodar o mesmo mês duas vezes e comparar contagens.
  4. Adicionar retry e timeout.
"""

from __future__ import annotations

import pendulum
from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

DBT_DIR = "/opt/airflow/dbt"


@dag(
    dag_id="elt_tlc",
    description="Ingestão + transformação (dbt) dos dados de táxi de NYC",
    schedule="0 6 1 * *",  # todo dia 1º, 06:00
    start_date=pendulum.datetime(2024, 1, 1, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": pendulum.duration(minutes=5)},
    tags=["elt", "tlc"],
)
def elt_tlc():
    month = "{{ (data_interval_start).strftime('%Y-%m') }}"

    ingest = BashOperator(
        task_id="ingest_raw",
        bash_command=f"python /opt/airflow/scripts/ingest.py --months {month}",
    )

    transform = BashOperator(
        task_id="dbt_build",
        bash_command=(
            f"cd {DBT_DIR} && "
            f"dbt build --profiles-dir . --vars '{{\"month\": \"{month}\"}}'"
        ),
    )

    # TODO: adicionar task de freshness (dbt source freshness) antes do build
    ingest >> transform


elt_tlc()
