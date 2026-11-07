"""Teste de integração da ingestão (F-01): idempotência por arquivo de origem.

Roda contra um Postgres descartável; sem banco acessível, o teste é pulado.
"""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

import ingest

COLUNAS = [
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "total_amount",
]


@pytest.fixture
def parquet_file(tmp_path):
    """Parquet pequeno e anonimizado, com o mesmo formato do arquivo da TLC."""
    df = pd.DataFrame(
        {
            "VendorID": [1, 2, 1, 2],
            "tpep_pickup_datetime": pd.to_datetime(
                [
                    "2024-01-01 08:00:00",
                    "2024-01-01 09:15:00",
                    "2024-01-02 18:30:00",
                    "2024-01-02 22:05:00",
                ]
            ),
            "tpep_dropoff_datetime": pd.to_datetime(
                [
                    "2024-01-01 08:20:00",
                    "2024-01-01 09:40:00",
                    "2024-01-02 18:55:00",
                    "2024-01-02 22:30:00",
                ]
            ),
            "passenger_count": [1, 2, 1, 3],
            "trip_distance": [1.5, 4.2, 0.8, 9.9],
            "PULocationID": [142, 236, 79, 132],
            "DOLocationID": [236, 142, 79, 265],
            "payment_type": [1, 1, 2, 1],
            "fare_amount": [12.5, 24.0, 6.0, 55.5],
            "total_amount": [15.0, 28.5, 8.0, 62.0],
        }
    )
    path = tmp_path / "yellow_tripdata_2024-01.parquet"
    df.to_parquet(path, index=False)
    return path, df


def _count(url: str, where: str = "") -> int:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(text(f"select count(*) from raw.yellow_trips {where}")).scalar()
    finally:
        engine.dispose()


def test_load_is_idempotent(raw_schema, parquet_file, monkeypatch):
    """Rodar a carga duas vezes com o mesmo arquivo não duplica linhas."""
    path, df = parquet_file
    monkeypatch.setattr(ingest, "DB_URL", raw_schema)

    assert ingest.load(path, "2024-01") == len(df)
    primeira = _count(raw_schema)

    ingest.load(path, "2024-01")
    segunda = _count(raw_schema)

    assert primeira == segunda == len(df)


def test_load_keeps_other_source_files(raw_schema, parquet_file, tmp_path, monkeypatch):
    """Cada arquivo é substituído isoladamente; os demais permanecem."""
    path, df = parquet_file
    monkeypatch.setattr(ingest, "DB_URL", raw_schema)

    ingest.load(path, "2024-01")
    outro = tmp_path / "yellow_tripdata_2024-02.parquet"
    pd.read_parquet(path).to_parquet(outro, index=False)
    ingest.load(outro, "2024-02")

    assert _count(raw_schema) == 2 * len(df)
    assert _count(raw_schema, "where _source_file = 'yellow_tripdata_2024-01.parquet'") == len(df)
    assert _count(raw_schema, "where _source_file = 'yellow_tripdata_2024-02.parquet'") == len(df)
