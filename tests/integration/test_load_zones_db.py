"""Teste de integração da carga de zonas (F-02): truncate+insert com 265 linhas.

Roda contra um Postgres descartável; sem banco acessível, o teste é pulado.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text

import load_zones


def _write_lookup(path, rows: int = load_zones.EXPECTED_ROWS) -> None:
    """Gera um lookup anonimizado com a mesma forma do CSV oficial."""
    pd.DataFrame(
        {
            "LocationID": range(1, rows + 1),
            "Borough": "Manhattan",
            "Zone": [f"Zone {i}" for i in range(1, rows + 1)],
            "Service_Zone": "Yellow Zone",
        }
    ).to_csv(path, index=False)


def _columns(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return set(
                conn.execute(
                    text(
                        "select column_name from information_schema.columns "
                        "where table_schema = 'raw' and table_name = 'taxi_zones'"
                    )
                ).scalars()
            )
    finally:
        engine.dispose()


def test_load_zones_loads_265_rows_and_is_idempotent(raw_schema, tmp_path, monkeypatch):
    """A carga completa as 265 linhas e repetir não duplica (truncate+insert)."""
    csv_path = tmp_path / "taxi_zone_lookup.csv"
    _write_lookup(csv_path)
    monkeypatch.setattr(load_zones, "DB_URL", raw_schema)

    assert load_zones.load(csv_path) == load_zones.EXPECTED_ROWS
    assert load_zones.load(csv_path) == load_zones.EXPECTED_ROWS
    assert load_zones.EXPECTED_COLUMNS.issubset(_columns(raw_schema))


def test_load_zones_replaces_previous_content(raw_schema, tmp_path, monkeypatch):
    """Uma carga menor substitui o conteúdo anterior em vez de acumular."""
    csv_path = tmp_path / "taxi_zone_lookup.csv"
    monkeypatch.setattr(load_zones, "DB_URL", raw_schema)

    _write_lookup(csv_path, rows=load_zones.EXPECTED_ROWS)
    assert load_zones.load(csv_path) == load_zones.EXPECTED_ROWS

    _write_lookup(csv_path, rows=3)
    assert load_zones.load(csv_path) == 3
