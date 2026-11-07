#!/usr/bin/env python3
"""Gera 3 gráficos do Projeto A a partir dos dados no Postgres.

Salva em /opt/airflow/data/graficos/ (volume compartilhado com ./data no WSL).

Uso (dentro do container airflow):
    python /opt/airflow/scripts/gerar_graficos.py

As funções `plot_*` recebem a conexão e o diretório de saída, o que permite
testá-las com uma conexão falsa (ver tests/unit/test_graficos.py).
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import psycopg2

OUT_DIR = Path(os.getenv("GRAFICOS_DIR", "/opt/airflow/data/graficos"))

DB_PARAMS = {
    "host": os.getenv("WAREHOUSE_HOST", "postgres"),
    "port": int(os.getenv("WAREHOUSE_PORT", "5432")),
    "dbname": os.getenv("WAREHOUSE_DB", "warehouse"),
    "user": os.getenv("POSTGRES_USER", "dw"),
    "password": os.getenv("POSTGRES_PASSWORD", "dw"),
}

COR = "#1f77b4"

plt.rcParams.update({
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "figure.dpi": 150,
})


def connect():
    """Abre a conexão com o warehouse (separado do import, para testabilidade)."""
    return psycopg2.connect(**DB_PARAMS)


def _query(conn, sql: str):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def plot_demand(conn, out_dir: Path) -> Path:
    """Gráfico 1: demanda por hora do dia."""
    rows = _query(conn, """
        SELECT
            EXTRACT(hour FROM pickup_at)::int AS hora,
            COUNT(*) AS viagens
        FROM marts.fct_trips
        GROUP BY 1
        ORDER BY 1;
    """)
    horas = [r[0] for r in rows]
    viagens = [r[1] for r in rows]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(horas, viagens, color=COR)
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Trips")
    ax.set_title("Ride demand by hour of day (3 months, 2024)")
    ax.set_xticks(range(24))
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    path = out_dir / "demanda_por_hora.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_fares(conn, out_dir: Path) -> Path:
    """Gráfico 2: ticket médio por zona (top 10)."""
    rows = _query(conn, """
        SELECT
            z.zone AS zona,
            ROUND(AVG(f.total_amount)::numeric, 2) AS ticket_medio
        FROM marts.fct_trips f
        JOIN marts.dim_zones z ON f.pickup_zone_id = z.zone_id
        GROUP BY z.zone
        ORDER BY ticket_medio DESC
        LIMIT 10;
    """)
    zonas = [r[0] for r in rows]
    tickets = [float(r[1]) for r in rows]
    # Inverter para exibir o maior em cima
    zonas = zonas[::-1]
    tickets = tickets[::-1]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(zonas, tickets, color=COR)
    ax.set_xlabel("Average fare (US$)")
    ax.set_ylabel("Pickup zone")
    ax.set_title("Top 10 zones by average fare (US$, 3 months 2024)")
    ax.grid(axis="x", alpha=0.3)
    for i, v in enumerate(tickets):
        ax.text(v + 1, i, f"${v:,.2f}", va="center")
    plt.tight_layout()
    path = out_dir / "ticket_por_zona.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_tips(conn, out_dir: Path) -> Path:
    """Gráfico 3: gorjeta por método de pagamento."""
    rows = _query(conn, """
        SELECT
            payment_method AS metodo,
            ROUND(avg_tip_pct * 100, 1) AS gorjeta_pct
        FROM marts.agg_payment_behavior
        WHERE payment_method IN ('credit_card', 'cash')
        ORDER BY gorjeta_pct DESC;
    """)
    metodos = [r[0] for r in rows]
    gorjetas = [float(r[1]) for r in rows]

    cores = [COR, "#ff7f0e"]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(metodos, gorjetas, color=cores[: len(metodos)])
    ax.set_xlabel("Payment method")
    ax.set_ylabel("Average tip (% of fare)")
    ax.set_title("Average tip by payment method (3 months 2024)")
    ax.grid(axis="y", alpha=0.3)
    for i, v in enumerate(gorjetas):
        ax.text(i, v + 0.5, f"{v}%", ha="center")
    plt.tight_layout()
    path = out_dir / "gorjeta_por_pagamento.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def generate_all(conn, out_dir: Path = OUT_DIR) -> list[Path]:
    """Gera os 3 gráficos e devolve os caminhos criados."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [plot_demand(conn, out_dir), plot_fares(conn, out_dir), plot_tips(conn, out_dir)]
    for i, path in enumerate(paths, start=1):
        print(f"[grafico {i}] {path}")
    return paths


def main() -> None:
    conn = connect()
    try:
        generate_all(conn)
    finally:
        conn.close()
    print("\nTodos os gráficos gerados com sucesso.")


if __name__ == "__main__":
    main()
