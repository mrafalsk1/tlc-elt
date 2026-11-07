"""Testes de unidade para scripts/gerar_graficos.py (F-08).

Não dependem de banco: usam uma conexão falsa e verificam os PNGs gerados.
"""

from __future__ import annotations

import gerar_graficos

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        self.sql = sql

    def fetchall(self):
        return self._rows


class FakeConnection:
    """Devolve um resultado pré-definido por query, na ordem das chamadas."""

    def __init__(self, results):
        self._results = list(results)
        self.queries: list[FakeCursor] = []

    def cursor(self):
        cur = FakeCursor(self._results.pop(0))
        self.queries.append(cur)
        return cur


def _results():
    return [
        [(hour, 1000 + hour * 10) for hour in range(24)],
        [(f"Zone {i}", 40.0 + i) for i in range(10)],
        [("credit_card", 22.5), ("cash", 5.0)],
    ]


def test_generate_all_writes_three_valid_pngs(tmp_path):
    """As 3 consultas viram 3 PNGs legíveis, com os nomes esperados."""
    paths = gerar_graficos.generate_all(FakeConnection(_results()), tmp_path)

    assert [p.name for p in paths] == [
        "demanda_por_hora.png",
        "ticket_por_zona.png",
        "gorjeta_por_pagamento.png",
    ]
    for path in paths:
        assert path.exists()
        data = path.read_bytes()
        assert data.startswith(PNG_MAGIC)
        assert len(data) > 5_000


def test_generate_all_creates_output_dir(tmp_path):
    """O diretório de saída é criado se não existir."""
    out_dir = tmp_path / "novo" / "graficos"
    assert not out_dir.exists()

    gerar_graficos.generate_all(FakeConnection(_results()), out_dir)

    assert out_dir.is_dir()
    assert len(list(out_dir.glob("*.png"))) == 3


def test_each_chart_uses_its_own_query(tmp_path):
    """Cada gráfico executa uma consulta distinta (sem reaproveitar resultado)."""
    conn = FakeConnection(_results())
    gerar_graficos.generate_all(conn, tmp_path)

    assert len(conn.queries) == 3
    sqls = [q.sql for q in conn.queries]
    assert len(set(sqls)) == 3
    assert "fct_trips" in sqls[0]
    assert "dim_zones" in sqls[1]
    assert "agg_payment_behavior" in sqls[2]
