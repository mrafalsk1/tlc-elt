"""Ingestão de NYC TLC yellow taxi trips para o schema `raw`.

Uso (dentro do container):
    python /opt/airflow/scripts/ingest.py --months 2024-01 2024-02 2024-03

Decisões:
  - O arquivo Parquet é baixado uma única vez para `data/raw` e reaproveitado
    (o `_source_file` guarda o nome do arquivo de origem).
  - A carga é idempotente: antes de inserir, apaga as linhas daquele arquivo.
  - A escrita usa `COPY ... FROM STDIN (FORMAT csv)`, ~10x mais rápido que
    `to_sql(..., method=None)`, que geraria um INSERT por linha.
  - As colunas são normalizadas para minúsculas porque o Postgres não distingue
    maiúsculas em identificadores não citados; a fonte traz `VendorID`,
    `PULocationID`, etc.
"""

from __future__ import annotations

import argparse
import io
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from sqlalchemy import create_engine, text

# Página oficial dos arquivos:
# https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"

RAW_DIR = Path(os.getenv("RAW_DIR", "/opt/airflow/data/raw"))

DB_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER', 'dw')}:"
    f"{os.getenv('POSTGRES_PASSWORD', 'dw')}@"
    f"{os.getenv('WAREHOUSE_HOST', 'postgres')}:"
    f"{os.getenv('WAREHOUSE_PORT', '5432')}/"
    f"{os.getenv('WAREHOUSE_DB', 'warehouse')}"
)

# Linhas por lote no COPY. 200k x ~21 colunas cabem com folga na memória.
CHUNK_ROWS = 200_000


def download(month: str) -> Path:
    """Baixa o Parquet do mês (YYYY-MM) e devolve o caminho local."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = RAW_DIR / f"yellow_tripdata_{month}.parquet"

    if target.exists() and target.stat().st_size > 0:
        print(f"[skip] {target.name} já existe ({target.stat().st_size / 1e6:.1f} MB)")
        return target

    url = BASE_URL.format(month=month)
    part = target.with_name(target.name + ".part")
    print(f"[download] {url}")

    started = time.time()
    with requests.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length") or 0)
        done = 0
        last_marked = 0.0
        with open(part, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                handle.write(chunk)
                done += len(chunk)
                if total:
                    pct = done * 100 / total
                    if pct - last_marked >= 10:
                        print(f"    {pct:5.1f}%  {done / 1e6:7.1f} / {total / 1e6:.1f} MB", flush=True)
                        last_marked = pct

    part.replace(target)  # só aparece com o nome final se o download terminou
    print(f"[download] ok em {time.time() - started:.0f}s -> {target.name}")
    return target


def _existing_columns(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            select column_name
            from information_schema.columns
            where table_schema = 'raw' and table_name = 'yellow_trips'
            order by ordinal_position
            """
        )
    ).scalars()
    return list(rows)


def _ensure_table(engine, df: pd.DataFrame) -> None:
    """Cria raw.yellow_trips na primeira execução; falha claro se o schema mudou."""
    with engine.begin() as conn:
        existing = _existing_columns(conn)
        if existing:
            missing = [c for c in df.columns if c not in existing]
            extra = [c for c in existing if c not in df.columns and c != "_loaded_at"]
            if missing or extra:
                raise SystemExit(
                    "Schema divergente entre o Parquet e raw.yellow_trips.\n"
                    f"  colunas ausentes na tabela: {missing}\n"
                    f"  colunas ausentes no arquivo: {extra}\n"
                    "Se a fonte mudou de verdade, recrie a tabela: "
                    "drop table raw.yellow_trips; e rode de novo."
                )
            return

    # Tabela vazia: deixa o pandas inferir os tipos a partir do próprio arquivo.
    df.head(0).to_sql("yellow_trips", engine, schema="raw", if_exists="append", index=False)
    print("[schema] raw.yellow_trips criada")


def load(parquet_path: Path, month: str) -> int:
    """Carrega o Parquet em raw.yellow_trips. Idempotente por arquivo de origem."""
    started = time.time()
    df = pd.read_parquet(parquet_path)

    # Postgres dobra identificadores não citados para minúsculas; a fonte usa
    # CamelCase (VendorID, PULocationID...). Normalizar aqui evita aspas em todo
    # modelo dbt a jusante.
    df.columns = [str(c).strip().lower() for c in df.columns]
    df["_source_file"] = parquet_path.name
    df["_loaded_at"] = datetime.now(timezone.utc)

    engine = create_engine(DB_URL)
    _ensure_table(engine, df)

    columns = list(df.columns)
    copy_sql = (
        f"copy raw.yellow_trips ({', '.join(columns)}) "
        "from stdin with (format csv, null '')"
    )

    with engine.begin() as conn:
        deleted = conn.execute(
            text("delete from raw.yellow_trips where _source_file = :f"),
            {"f": parquet_path.name},
        ).rowcount
        if deleted:
            print(f"[idempotência] removidas {deleted:,} linhas antigas de {month}")

        cursor = conn.connection.cursor()
        try:
            for start in range(0, len(df), CHUNK_ROWS):
                batch = df.iloc[start : start + CHUNK_ROWS]
                buffer = io.StringIO()
                batch.to_csv(buffer, index=False, header=False, na_rep="")
                buffer.seek(0)
                cursor.copy_expert(copy_sql, buffer)
        finally:
            cursor.close()

    print(f"[load] {month}: {len(df):,} linhas em {time.time() - started:.0f}s")
    return len(df)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", nargs="+", required=True, help="ex.: 2024-01 2024-02")
    args = parser.parse_args()

    summary: list[tuple[str, int]] = []
    for month in args.months:
        path = download(month)
        summary.append((month, load(path, month)))

    print("\n[resumo]")
    for month, rows in summary:
        print(f"  {month}: {rows:>10,} linhas")
    print(f"  total : {sum(r for _, r in summary):>10,} linhas")


if __name__ == "__main__":
    main()
