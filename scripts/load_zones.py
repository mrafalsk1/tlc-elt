#!/usr/bin/env python3
"""Carrega o lookup oficial de zonas da NYC TLC em `raw.taxi_zones`.

Uso (dentro do container):
    python /opt/airflow/scripts/load_zones.py

É uma tabela pequena (265 linhas) e muda raramente, então a carga é
truncate+insert: simples e idempotente. O CSV fica em `data/raw/` junto dos Parquets.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests
from sqlalchemy import create_engine, text

ZONES_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"

RAW_DIR = Path(os.getenv("RAW_DIR", "/opt/airflow/data/raw"))

DB_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER', 'dw')}:"
    f"{os.getenv('POSTGRES_PASSWORD', 'dw')}@"
    f"{os.getenv('WAREHOUSE_HOST', 'postgres')}:"
    f"{os.getenv('WAREHOUSE_PORT', '5432')}/"
    f"{os.getenv('WAREHOUSE_DB', 'warehouse')}"
)


def download() -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = RAW_DIR / "taxi_zone_lookup.csv"
    if target.exists() and target.stat().st_size > 0:
        print(f"[skip] {target.name} já existe")
        return target

    print(f"[download] {ZONES_URL}")
    response = requests.get(ZONES_URL, timeout=60)
    response.raise_for_status()
    part = target.with_name(target.name + ".part")
    part.write_bytes(response.content)
    part.replace(target)
    return target


def load(csv_path: Path) -> int:
    df = pd.read_csv(csv_path)
    df.columns = [str(c).strip().lower() for c in df.columns]

    # O lookup tem 265 linhas; qualquer coisa muito diferente disso é arquivo errado.
    if not {"locationid", "borough", "zone", "service_zone"}.issubset(df.columns):
        raise SystemExit(f"colunas inesperadas no lookup: {list(df.columns)}")

    engine = create_engine(DB_URL)
    df.to_sql("taxi_zones", engine, schema="raw", if_exists="replace", index=False)

    with engine.begin() as conn:
        total = conn.execute(text("select count(*) from raw.taxi_zones")).scalar()
    print(f"[load] raw.taxi_zones: {total} linhas")
    return int(total)


def main() -> None:
    load(download())


if __name__ == "__main__":
    main()
