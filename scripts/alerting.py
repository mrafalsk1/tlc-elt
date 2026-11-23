"""Alertas locais do DAG elt_tlc: JSONL append-only + webhook opcional.

Só stdlib. Todo alerta vira uma linha JSON em ALERTS_FILE (padrão:
data/alerts/alerts.jsonl). Se ALERT_WEBHOOK_URL estiver definida, o mesmo
payload também é enviado por POST. Falha de webhook nunca propaga.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SOURCE = "tlc-elt"
DEFAULT_ALERTS_FILE = Path(__file__).resolve().parents[1] / "data" / "alerts" / "alerts.jsonl"
WEBHOOK_TIMEOUT_S = 5

FIELDS = (
    "ts",
    "source",
    "type",
    "severity",
    "dag_id",
    "task_id",
    "run_id",
    "logical_date",
    "message",
    "details",
)


def write_alert(entry: dict[str, Any], path: str | None = None) -> None:
    # Cada linha é um único write() em modo "a" (O_APPEND): para linhas pequenas
    # o append é atômico no POSIX. Concorrência alta ou FS de rede (SMB/NFS) não
    # têm essa garantia; isso é limite conhecido, não tratado aqui.
    target = Path(path or os.getenv("ALERTS_FILE") or DEFAULT_ALERTS_FILE)
    row = {key: entry.get(key) for key in FIELDS}
    row["ts"] = datetime.now(UTC).isoformat()
    row["source"] = SOURCE
    row["details"] = row["details"] or {}

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def notify_webhook(entry: dict[str, Any]) -> None:
    url = os.getenv("ALERT_WEBHOOK_URL")
    if not url:
        return
    body = json.dumps(entry, ensure_ascii=False, default=str).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT_S):
            pass
    except Exception as exc:  # noqa: BLE001 - webhook nunca pode derrubar o DAG
        # A URL não é logada: pode conter token. Só o tipo e a mensagem curta.
        log.warning(
            "Falha ao enviar alerta para o webhook (%s: %s); alerta segue no JSONL",
            type(exc).__name__,
            str(exc)[:200],
        )


def _emit(entry: dict[str, Any]) -> None:
    # Nunca levanta: alerta quebrado não pode mascarar a falha original da task.
    try:
        write_alert(entry)
    except Exception as exc:  # noqa: BLE001 - alerta nunca mascara a falha da task
        log.warning("Falha ao gravar alerta em JSONL (%s: %s)", type(exc).__name__, str(exc)[:200])
    notify_webhook(entry)


def alert_failure(context: dict[str, Any]) -> None:
    ti = context["task_instance"]
    exception = context.get("exception")
    logical_date = context.get("logical_date")
    _emit(
        {
            "type": "task_failure",
            "severity": "critical",
            "dag_id": ti.dag_id,
            "task_id": ti.task_id,
            "run_id": context.get("run_id"),
            "logical_date": logical_date.isoformat() if logical_date else None,
            "message": str(exception) if exception else "task falhou sem exceção registrada",
            "details": {
                "try_number": getattr(ti, "try_number", None),
                "max_tries": getattr(ti, "max_tries", None),
                "log_url": getattr(ti, "log_url", None),
            },
        }
    )

