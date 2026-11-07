"""Fixtures dos testes de integração.

Usam um Postgres descartável (por padrão o banco `postgres`), nunca o
`warehouse` real. Se o banco não estiver acessível, os testes são pulados.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text


def _env(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def build_test_db_url() -> str:
    """URL do banco de teste, a partir das mesmas variáveis dos scripts."""
    host = _env("WAREHOUSE_HOST_LOCAL", "WAREHOUSE_HOST", default="postgres")
    port = _env("WAREHOUSE_PORT_LOCAL", "WAREHOUSE_PORT", default="5432")
    user = _env("POSTGRES_USER", default="dw")
    password = _env("POSTGRES_PASSWORD", default="dw")
    dbname = _env("TEST_PG_DB", default="postgres")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"


@pytest.fixture(scope="session")
def pg_url() -> str:
    """URL de um banco descartável; pula a integração se não houver Postgres."""
    url = build_test_db_url()
    dbname = url.rsplit("/", 1)[-1]
    if dbname == _env("WAREHOUSE_DB", default="warehouse"):
        pytest.skip("TEST_PG_DB aponta para o warehouse; use um banco descartável")

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001 - qualquer falha de conexão vira skip
        pytest.skip(f"Postgres indisponível ({url.split('@')[-1]}): {type(exc).__name__}")
    finally:
        engine.dispose()
    return url


@pytest.fixture
def raw_schema(pg_url: str):
    """Schema raw vazio no banco de teste; limpa as tabelas antes e depois."""
    engine = create_engine(pg_url)
    with engine.begin() as conn:
        conn.execute(text("drop table if exists raw.yellow_trips"))
        conn.execute(text("drop table if exists raw.taxi_zones"))
        conn.execute(text("create schema if not exists raw"))
    yield pg_url
    with engine.begin() as conn:
        conn.execute(text("drop table if exists raw.yellow_trips"))
        conn.execute(text("drop table if exists raw.taxi_zones"))
    engine.dispose()
