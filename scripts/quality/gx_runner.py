"""Executa EXPECTATIONS (rules.py) com o Great Expectations 1.x.

ÚNICO arquivo do projeto que importa great_expectations. O pytest nunca importa
este módulo (ele exige GX instalado, que só existe em .venv-quality).
"""

from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("GX_ANALYTICS_ENABLED", "false")
os.environ.setdefault("TQDM_DISABLE", "1")

import great_expectations as gx
import pandas as pd
from great_expectations import expectations as E

from quality import rules


def _gx_expectation(exp: rules.Expectation, zone_ids: list[int]) -> Any | None:
    if exp.kind == "not_null":
        return E.ExpectColumnValuesToNotBeNull(column=exp.column)
    if exp.kind == "between":
        return E.ExpectColumnValuesToBeBetween(
            column=exp.column, min_value=exp.params["min"], max_value=exp.params["max"]
        )
    if exp.kind == "fk":
        return E.ExpectColumnValuesToBeInSet(column=exp.column, value_set=zone_ids)
    if exp.kind == "in_set":
        return E.ExpectColumnValuesToBeInSet(column=exp.column, value_set=exp.params["values"])
    if exp.kind == "row_count":
        return E.ExpectTableRowCountToBeBetween(
            min_value=exp.params["min"], max_value=exp.params["max"]
        )
    return None  # dropoff_after_pickup: avaliada em Pandas (ver run_suite)


def run_suite(df: pd.DataFrame, zones: pd.DataFrame, batch_key: str) -> dict[str, Any]:
    """Valida df com GX e devolve o mesmo formato de rules.validate_frame."""
    zone_ids = sorted(set(zones["LocationID"].astype(int)))
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(f"src_{batch_key}")
    asset = data_source.add_dataframe_asset(name="trips")
    batch_definition = asset.add_batch_definition_whole_dataframe("whole")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    results = []
    for exp in rules.EXPECTATIONS:
        gx_exp = _gx_expectation(exp, zone_ids)
        if gx_exp is None:
            mask = rules._violation_mask(df, exp, set(zone_ids))
            violations = int(mask.sum())
        else:
            outcome = batch.validate(gx_exp)
            passed = bool(outcome.success)
            violations = 0 if passed else int(outcome.result.get("unexpected_count") or 1)
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
