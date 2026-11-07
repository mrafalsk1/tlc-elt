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

EXPECTED_COLUMNS = {"locationid", "borough", "zone", "service_zone"}
EXPECTED_ROWS = 265


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
    if not EXPECTED_COLUMNS.issubset(df.columns):
        raise SystemExit(f"colunas inesperadas no lookup: {list(df.columns)}")
    if len(df) != EXPECTED_ROWS:
        print(f"[aviso] lookup com {len(df)} linhas (esperado {EXPECTED_ROWS})")

    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        conn.execute(text("create schema if not exists raw"))
        exists = conn.execute(text("select to_regclass('raw.taxi_zones')")).scalar() is not None

    if not exists:
        # Cria a tabela vazia com os tipos inferidos do próprio CSV.
        df.head(0).to_sql("taxi_zones", engine, schema="raw", if_exists="append", index=False)

    # truncate+insert: idempotente e preserva a estrutura da tabela
    # (um `if_exists="replace"` derrubaria índices/grants a cada carga).
    with engine.begin() as conn:
        conn.execute(text("truncate table raw.taxi_zones"))

    df.to_sql("taxi_zones", engine, schema="raw", if_exists="append", index=False)

    with engine.connect() as conn:
        total = conn.execute(text("select count(*) from raw.taxi_zones")).scalar()
    print(f"[load] raw.taxi_zones: {total} linhas")
    return int(total)


def main() -> None:
    load(download())


if __name__ == "__main__":
    main()
