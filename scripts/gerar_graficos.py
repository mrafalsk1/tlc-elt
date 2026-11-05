"""Gera 3 gráficos do Projeto A a partir dos dados no Postgres.

Salva em /opt/airflow/data/graficos/ (volume compartilhado com ./data no WSL).

Uso (dentro do container airflow):
    python /opt/airflow/scripts/gerar_graficos.py
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import psycopg2

OUT_DIR = Path(os.getenv("GRAFICOS_DIR", "/opt/airflow/data/graficos"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

DB_URL = {
    "host": os.getenv("WAREHOUSE_HOST", "postgres"),
    "port": int(os.getenv("WAREHOUSE_PORT", "5432")),
    "dbname": os.getenv("WAREHOUSE_DB", "warehouse"),
    "user": os.getenv("POSTGRES_USER", "dw"),
    "password": os.getenv("POSTGRES_PASSWORD", "dw"),
}

conn = psycopg2.connect(**DB_URL)

plt.rcParams.update({
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "figure.dpi": 150,
})

COR = "#1f77b4"


def query(sql: str):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


# ------------------------------------------------------------
# Gráfico 1: Demanda por hora do dia
# ------------------------------------------------------------
rows = query("""
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
ax.set_xlabel("Hora do dia")
ax.set_ylabel("Viagens")
ax.set_title("Demanda de corridas por hora do dia (3 meses, 2024)")
ax.set_xticks(range(0, 24))
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_DIR / "demanda_por_hora.png", bbox_inches="tight")
plt.close()
print(f"[grafico 1] {OUT_DIR / 'demanda_por_hora.png'}")

# ------------------------------------------------------------
# Gráfico 2: Ticket médio por zona (top 10)
# ------------------------------------------------------------
rows = query("""
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
ax.set_xlabel("Ticket médio (US$)")
ax.set_ylabel("Zona de embarque")
ax.set_title("Top 10 zonas por ticket médio (US$, 3 meses 2024)")
ax.grid(axis="x", alpha=0.3)
for i, v in enumerate(tickets):
    ax.text(v + 1, i, f"${v:,.2f}", va="center")
plt.tight_layout()
plt.savefig(OUT_DIR / "ticket_por_zona.png", bbox_inches="tight")
plt.close()
print(f"[grafico 2] {OUT_DIR / 'ticket_por_zona.png'}")

# ------------------------------------------------------------
# Gráfico 3: Gorjeta por método de pagamento
# ------------------------------------------------------------
rows = query("""
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
ax.set_xlabel("Método de pagamento")
ax.set_ylabel("Gorjeta média (% da tarifa)")
ax.set_title("Gorjeta média por método de pagamento (3 meses 2024)")
ax.grid(axis="y", alpha=0.3)
for i, v in enumerate(gorjetas):
    ax.text(i, v + 0.5, f"{v}%", ha="center")
plt.tight_layout()
plt.savefig(OUT_DIR / "gorjeta_por_pagamento.png", bbox_inches="tight")
plt.close()
print(f"[grafico 3] {OUT_DIR / 'gorjeta_por_pagamento.png'}")

conn.close()
print("\nTodos os gráficos gerados com sucesso.")
