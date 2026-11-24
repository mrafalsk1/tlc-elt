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
        # Só o tipo: ValueError("unknown url type: '<url>'") pode conter o segredo.
        log.warning(
            "Falha ao enviar alerta para o webhook (%s); alerta segue no JSONL",
            type(exc).__name__,
        )


def _emit(entry: dict[str, Any], path: str | None = None) -> None:
    # Nunca levanta: alerta quebrado não pode mascarar a falha original da task.
    try:
        write_alert(entry, path=path)
    except Exception as exc:  # noqa: BLE001 - alerta nunca mascara a falha da task
        log.warning("Falha ao gravar alerta em JSONL (%s: %s)", type(exc).__name__, str(exc)[:200])
    notify_webhook(entry)


def alert_dagrun_failure(context: dict[str, Any]) -> None:
    # Callback de DAG: roda quando o run inteiro falha, p.ex. por dagrun_timeout
    # (nesse caso não há task_instance no contexto). Tolerante a dados faltando.
    dag = context.get("dag")
    dag_run = context.get("dag_run")
    run_id = context.get("run_id") or getattr(dag_run, "run_id", None)
    logical_date = context.get("logical_date") or getattr(dag_run, "logical_date", None)
    dag_id = getattr(dag, "dag_id", None) or getattr(dag_run, "dag_id", None)
    reason = context.get("reason") or context.get("msg")
    _emit(
        {
            "type": "dagrun_failure",
            "severity": "critical",
            "dag_id": dag_id,
            "task_id": None,
            "run_id": run_id,
            "logical_date": logical_date.isoformat() if logical_date else None,
            "message": f"run falhou ({reason})" if reason else "run falhou",
            "details": {
                "state": str(getattr(dag_run, "state", None)),
                "start_date": _iso(getattr(dag_run, "start_date", None)),
            },
        }
    )


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


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

