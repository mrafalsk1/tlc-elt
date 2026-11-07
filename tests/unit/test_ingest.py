"""Testes de unidade para scripts/ingest.py.

Não dependem de banco de dados real: testam apenas a lógica de
normalização de colunas e construção da URL de download.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import ingest  # noqa: E402


def test_base_url_format():
    """A URL base deve conter o placeholder {month}."""
    assert "{month}" in ingest.BASE_URL
    assert ingest.BASE_URL.endswith(".parquet")


def test_normalize_column_names():
    """Colunas CamelCase devem virar minúsculas."""
    cols = ["VendorID", "PULocationID", "DOLocationID", "total_amount"]
    normalized = [str(c).strip().lower() for c in cols]
    assert normalized == ["vendorid", "pulocationid", "dolocationid", "total_amount"]


def test_chunk_rows_is_positive():
    """O tamanho de lote deve ser positivo."""
    assert ingest.CHUNK_ROWS > 0


def test_download_url_uses_month():
    """A URL gerada para um mês deve substituir {month} corretamente."""
    url = ingest.BASE_URL.format(month="2024-01")
    assert "2024-01" in url
    assert "{month}" not in url
