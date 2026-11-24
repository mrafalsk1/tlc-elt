#!/usr/bin/env python3
"""Gera 3 gráficos do Projeto A a partir dos dados no Postgres.

Salva em /opt/airflow/data/graficos/ (volume compartilhado com ./data no WSL).
Todos os textos das figuras são em inglês, porque o README é em inglês.

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
ZONAS_MIN_VIAGENS = 5_000  # evita que uma zona com 3 corridas de US$ 200 lidere o ticket médio

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
    """Gráfico 1: viagens válidas por hora do dia."""
    rows = _query(conn, """
        SELECT
            EXTRACT(hour FROM pickup_at)::int AS hour_of_day,
            COUNT(*) AS trips
        FROM marts.fct_trips
        WHERE is_valid_trip
        GROUP BY 1
        ORDER BY 1;
    """)
    horas = [r[0] for r in rows]
    viagens = [r[1] for r in rows]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(horas, viagens, color=COR)
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Valid trips")
    ax.set_title("Trips by hour of day (Jan-Mar 2024)")
    ax.set_xticks(range(24))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    path = out_dir / "demand_by_hour.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_fares(conn, out_dir: Path) -> Path:
    """Gráfico 2: ticket médio por zona (top 10, só zonas com volume)."""
    rows = _query(conn, f"""
        SELECT
            z.zone AS pickup_zone,
            ROUND(AVG(f.total_amount)::numeric, 2) AS avg_fare
        FROM marts.fct_trips f
        JOIN marts.dim_zones z ON f.pickup_zone_id = z.zone_id
        WHERE f.is_valid_trip
        GROUP BY z.zone
        HAVING COUNT(*) >= {ZONAS_MIN_VIAGENS}
        ORDER BY avg_fare DESC
        LIMIT 10;
    """)
    zonas = [r[0] for r in rows]
    tickets = [float(r[1]) for r in rows]
    # Inverter para exibir o maior em cima
    zonas = zonas[::-1]
    tickets = tickets[::-1]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(zonas, tickets, color=COR)
    ax.set_xlabel("Average ticket (US$)")
    ax.set_ylabel("Pickup zone")
    ax.set_title("Top 10 zones by average ticket (Jan-Mar 2024)")
    ax.grid(axis="x", alpha=0.3)
    for i, v in enumerate(tickets):
        ax.text(v + 1, i, f"${v:,.2f}", va="center")
    plt.tight_layout()
    path = out_dir / "avg_fare_by_zone.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_tips(conn, out_dir: Path) -> Path:
    """Gráfico 3: gorjeta como % da tarifa, por método de pagamento.

    A média é ponderada pelo valor: sum(tips) / sum(fare). Média simples de
    `avg_tip_pct` mistura faixas de gorjeta e dá um número que não é o do README.
    """
    rows = _query(conn, """
        SELECT
            payment_method,
            ROUND(
                (SUM(total_tips) / NULLIF(SUM(total_fare), 0))::numeric * 100, 1
            ) AS tip_pct,
            SUM(trips) AS trips
        FROM marts.agg_payment_behavior
        WHERE payment_method IN ('credit_card', 'cash')
        GROUP BY 1
        ORDER BY 2 DESC;
    """)
    metodos = [r[0] for r in rows]
    gorjetas = [float(r[1]) for r in rows]

    cores = [COR, "#ff7f0e"]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(metodos, gorjetas, color=cores[: len(metodos)])
    ax.set_xlabel("Payment method")
    ax.set_ylabel("Tips (% of fare)")
    ax.set_title("Average tip by payment method (Jan-Mar 2024)")
    ax.set_ylim(0, max(gorjetas) * 1.25 if gorjetas else 1)
    ax.grid(axis="y", alpha=0.3)
    for i, v in enumerate(gorjetas):
        ax.text(i, v + 0.4, f"{v}%", ha="center")
    fig.text(
        0.5,
        0.01,
        "Cash tips are not recorded by the meter; 0% is not a behavioural finding.",
        ha="center",
        fontsize=8,
        style="italic",
    )
    plt.tight_layout(rect=(0, 0.04, 1, 1))
    path = out_dir / "tip_by_payment_method.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def generate_all(conn, out_dir: Path = OUT_DIR) -> list[Path]:
    """Gera os 3 gráficos e devolve os caminhos criados."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [plot_demand(conn, out_dir), plot_fares(conn, out_dir), plot_tips(conn, out_dir)]
    for i, path in enumerate(paths, start=1):
        print(f"[chart {i}] {path}")
    return paths


def main() -> None:
    conn = connect()
    try:
        generate_all(conn)
    finally:
        conn.close()
    print("\nAll charts generated successfully.")


if __name__ == "__main__":
    main()
