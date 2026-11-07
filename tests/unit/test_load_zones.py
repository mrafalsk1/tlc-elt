"""Testes de unidade para scripts/load_zones.py.

Não dependem de banco de dados real: testam apenas a lógica de validação
de colunas e normalização de nomes.
"""

import sys
from pathlib import Path

# Adiciona scripts/ ao path para importar load_zones
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import load_zones  # noqa: E402


EXPECTED_COLUMNS = {"locationid", "borough", "zone", "service_zone"}


def test_normalized_columns_match_expected():
    """As colunas normalizadas do lookup devem conter todas as esperadas."""
    df_columns = ["LocationID", "borough", "zone", "service_zone"]
    normalized = [str(c).strip().lower() for c in df_columns]
    assert EXPECTED_COLUMNS.issubset(set(normalized))


def test_unexpected_columns_raise():
    """Colunas inesperadas devem ser detectadas."""
    df_columns = ["locationid", "borough", "zone", "coluna_inesperada"]
    assert not EXPECTED_COLUMNS.issubset(set(df_columns))


def test_zones_url_is_valid():
    """A URL do lookup deve ser HTTPS e apontar para a fonte oficial."""
    assert load_zones.ZONES_URL.startswith("https://")
    assert "taxi_zone_lookup.csv" in load_zones.ZONES_URL
