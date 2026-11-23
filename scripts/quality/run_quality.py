#!/usr/bin/env python3
"""CLI de qualidade: valida um Parquet do raw e grava alerta em alerts.jsonl.

Uso (no .venv-quality, que tem GX):
  python scripts/quality/run_quality.py --input data/raw/yellow_tripdata_2024-01.parquet \
      --zones data/raw/taxi_zone_lookup.csv [--out data/alerts/alerts.jsonl] [--limit N]

Exit code: 1 se qualquer expectativa critical falhar; 0 caso contrário.
O gx_runner é importado só dentro de main(): importar este módulo não exige GX,
então o pytest pode importar run_quality sem instalar o Great Expectations.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import alerting

from quality import rules


def load_zones(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def load_trips(path: Path, limit: int | None) -> pd.DataFrame:
    cols = [
        rules.PICKUP,
        rules.DROPOFF,
        rules.PU_ZONE,
        rules.DO_ZONE,
        rules.FARE,
        rules.DISTANCE,
        rules.PAYMENT,
    ]
    if path.suffix == ".csv":
        df = pd.read_csv(path, parse_dates=[rules.PICKUP, rules.DROPOFF], usecols=cols)
    else:
        df = pd.read_parquet(path, columns=cols)
    return df.head(limit) if limit else df


def build_alert(report: dict[str, Any], input_name: str) -> dict[str, Any] | None:
    failed = [r for r in report["results"] if not r["passed"]]
    if not failed:
        return None
    has_critical = any(r["severity"] == "critical" and not r["passed"] for r in report["results"])
    return {
        "type": "data_quality",
        "severity": "critical" if has_critical else "warning",
        "dag_id": None,
        "task_id": None,
        "run_id": None,
        "logical_date": None,
        "message": f"{len(failed)} expectativa(s) falharam em {input_name}",
        "details": {
            "input": input_name,
            "rows": report["rows"],
            "violations": {r["id"]: r["violations"] for r in report["results"]},
            "failed": [r["id"] for r in failed],
        },
    }


def run(input_path: Path, zones_path: Path, out: str | None, limit: int | None, engine: Any) -> int:
    zones = load_zones(zones_path)
    trips = load_trips(input_path, limit)
    report = engine.run_suite(trips, zones, batch_key=input_path.stem)
    alert = build_alert(report, input_path.name)
    if alert is not None:
        alerting.write_alert(alert, path=out)
        alerting.notify_webhook(alert)
    for r in report["results"]:
        flag = "OK  " if r["passed"] else "FAIL"
        print(f"{flag} [{r['severity']:8}] {r['id']:24} violações={r['violations']}")
    critical_failed = any(
        r["severity"] == "critical" and not r["passed"] for r in report["results"]
    )
    return 1 if critical_failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--zones", required=True, type=Path)
    parser.add_argument("--out", default=None, help="caminho do alerts.jsonl (padrão: ALERTS_FILE)")
    parser.add_argument("--limit", type=int, default=None, help="só as N primeiras linhas")
    args = parser.parse_args(argv)

    from quality import gx_runner  # import tardio: só quem roda a CLI precisa de GX

    return run(args.input, args.zones, args.out, args.limit, gx_runner)


if __name__ == "__main__":
    sys.exit(main())
