"""Regras de qualidade do ELT de táxi, em Pandas puro (sem Great Expectations).

Opera sobre o schema cru (Parquet/raw.yellow_trips), com os nomes do Parquet
(CamelCase). O dbt normaliza depois (staging.stg_yellow_trips); aqui não há
renomeação. gx_runner.py traduz EXPECTATIONS para uma suite do GX.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

PICKUP = "tpep_pickup_datetime"
DROPOFF = "tpep_dropoff_datetime"
PU_ZONE = "PULocationID"
DO_ZONE = "DOLocationID"
FARE = "fare_amount"
DISTANCE = "trip_distance"
PAYMENT = "payment_type"

# Contagem por lote: só a guarda de lote vazio. O máximo ainda não foi medido
# (medir ao longo de meses e registrar em docs/DATA_CONTRACTS.md antes de fixar).
BATCH_ROWS_MIN = 1
BATCH_ROWS_MAX = None


@dataclass(frozen=True)
class Expectation:
    id: str
    column: str | None
    kind: str
    severity: str  # "critical" | "warning"
    message: str
    params: dict[str, Any]


EXPECTATIONS: list[Expectation] = [
    Expectation("fare_not_null", FARE, "not_null", "critical", "tarifa nula", {}),
    Expectation(
        "fare_between", FARE, "between", "critical", "tarifa fora de [0, 500]", {"min": 0, "max": 500}
    ),
    Expectation(
        "distance_not_null", DISTANCE, "not_null", "critical", "distância nula", {}
    ),
    Expectation(
        "distance_between",
        DISTANCE,
        "between",
        "warning",
        "distância fora de [0, 200] milhas",
        {"min": 0, "max": 200},
    ),
    Expectation(
        "dropoff_after_pickup",
        None,
        "dropoff_after_pickup",
        "critical",
        "dropoff não é posterior ao pickup",
        {},
    ),
    Expectation(
        "pickup_zone_fk", PU_ZONE, "fk", "critical", "zona de embarque fora do lookup", {}
    ),
    Expectation(
        "dropoff_zone_fk", DO_ZONE, "fk", "critical", "zona de desembarque fora do lookup", {}
    ),
    Expectation(
        "payment_in_set",
        PAYMENT,
        "in_set",
        "warning",
        "payment_type fora de 0-6",
        {"values": [0, 1, 2, 3, 4, 5, 6]},
    ),
    Expectation(
        "batch_rows_between",
        None,
        "row_count",
        "critical",
        "contagem de linhas do lote fora da faixa",
        {"min": BATCH_ROWS_MIN, "max": BATCH_ROWS_MAX},
    ),
]


def _violation_mask(df: pd.DataFrame, exp: Expectation, zones: set[int]) -> pd.Series | None:
    """Máscara booleana das linhas que violam a expectativa (None para row_count)."""
    kind = exp.kind
    if kind == "not_null":
        return df[exp.column].isna()
    if kind == "between":
        col = df[exp.column]
        return col.notna() & ((col < exp.params["min"]) | (col > exp.params["max"]))
    if kind == "dropoff_after_pickup":
        return ~(df[DROPOFF] > df[PICKUP])
    if kind == "fk":
        return ~df[exp.column].isin(zones)
    if kind == "in_set":
        return df[exp.column].notna() & ~df[exp.column].isin(exp.params["values"])
    if kind == "row_count":
        return None
    raise ValueError(f"tipo de expectativa desconhecido: {kind}")


def validate_frame(
    df: pd.DataFrame, zones: pd.DataFrame, batch_key: str
) -> dict[str, Any]:
    """Avalia EXPECTATIONS sobre df e devolve contagem de violações por regra.

    Retorna {"batch_key", "rows", "results": [{id, severity, message, violations, passed}]}.
    Não levanta por violação: quem decide é o chamador (gx_runner / run_quality).
    """
    zone_ids = set(zones["LocationID"].astype(int))
    results = []
    for exp in EXPECTATIONS:
        if exp.kind == "row_count":
            n = len(df)
            too_small = n < exp.params["min"]
            too_big = exp.params["max"] is not None and n > exp.params["max"]
            violations = 1 if (too_small or too_big) else 0
        else:
            mask = _violation_mask(df, exp, zone_ids)
            violations = int(mask.sum())
        results.append(
            {
                "id": exp.id,
                "severity": exp.severity,
                "message": exp.message,
                "violations": violations,
                "passed": violations == 0,
            }
        )
    return {"batch_key": batch_key, "rows": len(df), "results": results}
