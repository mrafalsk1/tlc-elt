"""Fluxo mínimo em Dagster, para comparar com o DAG de Airflow (lacuna 8).

Escopo de propósito pequeno: dois assets (leitura do Parquet cru e agregação
diária em DuckDB) e um schedule mensal. Não substitui o dbt nem o Airflow; existe
para responder, em entrevista, como seria o mesmo pipeline com orquestração por
assets (lineage explícito, materialização por partição, tipagem entre etapas).
"""

from __future__ import annotations

import glob
from pathlib import Path

import pandas as pd
from dagster import Definitions, ScheduleDefinition, asset, define_asset_job
from dagster_duckdb import DuckDBResource

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_GLOB = str(REPO_ROOT / "data" / "raw" / "yellow_tripdata_*.parquet")
DB_PATH = REPO_ROOT / "data" / "dagster.duckdb"

COLUMNS = ["tpep_pickup_datetime", "total_amount"]


@asset(group_name="tlc", compute_kind="python")
def raw_trips() -> pd.DataFrame:
    """Lê o mês mais antigo do Parquet cru (mesma fonte do Projeto A)."""
    path = min(glob.glob(RAW_GLOB))
    return pd.read_parquet(path, columns=COLUMNS)


@asset(group_name="tlc", compute_kind="duckdb")
def daily_agg(raw_trips: pd.DataFrame, duckdb: DuckDBResource) -> int:
    """Agrega viagens e receita por dia e materializa em DuckDB.

    Retorna o número de linhas gravadas — é o número que o smoke test confere.
    """
    df = raw_trips.copy()
    df["trip_date"] = pd.to_datetime(df["tpep_pickup_datetime"]).dt.date
    agg = (
        df.groupby("trip_date", as_index=False)
        .agg(trips=("total_amount", "size"), revenue=("total_amount", "sum"))
        .sort_values("trip_date")
    )
    with duckdb.get_connection() as conn:
        # register explicito: a dependencia do DataFrame fica visivel ao linter.
        conn.register("daily_agg_input", agg)
        conn.execute("CREATE OR REPLACE TABLE daily_agg AS SELECT * FROM daily_agg_input")
        conn.unregister("daily_agg_input")
        rows = conn.execute("SELECT count(*) FROM daily_agg").fetchone()[0]
    return int(rows)


daily_agg_job = define_asset_job("daily_agg_job", selection=[raw_trips, daily_agg])

monthly_refresh = ScheduleDefinition(
    name="monthly_tlc_refresh",
    job=daily_agg_job,
    cron_schedule="0 6 1 * *",  # mesmo calendário do DAG de Airflow
)

definitions = Definitions(
    assets=[raw_trips, daily_agg],
    jobs=[daily_agg_job],
    schedules=[monthly_refresh],
    resources={"duckdb": DuckDBResource(database=str(DB_PATH))},
)
