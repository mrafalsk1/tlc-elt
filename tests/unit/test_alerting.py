"""Testes de unidade para scripts/alerting.py.

Não tocam em rede nem em Airflow: usam ALERTS_FILE em tmp_path e fakes.
"""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import alerting

FIELDS = {
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
}


@pytest.fixture
def alerts_file(tmp_path, monkeypatch):
    path = tmp_path / "alerts.jsonl"
    monkeypatch.setenv("ALERTS_FILE", str(path))
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    return path


def _read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_write_alert_appends_valid_jsonl(alerts_file):
    alerting.write_alert({"type": "a", "severity": "info"})
    alerting.write_alert({"type": "b", "severity": "warning"})

    rows = _read_lines(alerts_file)
    assert [r["type"] for r in rows] == ["a", "b"]
    for row in rows:
        assert set(row) == FIELDS
        assert row["source"] == "tlc-elt"
        assert datetime.fromisoformat(row["ts"]).tzinfo is not None


def test_write_alert_creates_parent_directory(tmp_path):
    path = tmp_path / "novo" / "dir" / "alerts.jsonl"
    alerting.write_alert({"type": "x"}, path=str(path))
    assert path.exists()


def test_notify_webhook_without_url_does_nothing(monkeypatch):
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)

    def boom(*args, **kwargs):
        raise AssertionError("não deveria chamar urlopen")

    monkeypatch.setattr(alerting.urllib.request, "urlopen", boom)
    alerting.notify_webhook({"type": "x"})


def test_notify_webhook_failure_does_not_propagate(monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "http://invalido.local/hook")

    def fail(*args, **kwargs):
        raise OSError("sem rede")

    monkeypatch.setattr(alerting.urllib.request, "urlopen", fail)
    alerting.notify_webhook({"type": "x"})


def test_alert_failure_builds_expected_fields(alerts_file):
    ti = SimpleNamespace(
        dag_id="elt_tlc",
        task_id="ingest_raw",
        try_number=1,
        max_tries=2,
        log_url="http://airflow/log",
    )
    context = {
        "task_instance": ti,
        "run_id": "scheduled__2026-11-01",
        "logical_date": datetime(2026, 11, 1, tzinfo=timezone.utc),
        "exception": RuntimeError("download falhou"),
    }

    alerting.alert_failure(context)

    (row,) = _read_lines(alerts_file)
    assert set(row) == FIELDS
    assert row["type"] == "task_failure"
    assert row["severity"] == "critical"
    assert row["dag_id"] == "elt_tlc"
    assert row["task_id"] == "ingest_raw"
    assert row["run_id"] == "scheduled__2026-11-01"
    assert row["logical_date"] == "2026-11-01T00:00:00+00:00"
    assert row["message"] == "download falhou"
    assert row["details"]["try_number"] == 1


def test_alert_failure_calls_webhook_with_same_payload(alerts_file, monkeypatch):
    sent = []
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "http://hook.local/x")
    monkeypatch.setattr(alerting, "notify_webhook", lambda entry: sent.append(entry))

    ti = SimpleNamespace(dag_id="elt_tlc", task_id="dbt_build")
    alerting.alert_failure({"task_instance": ti, "exception": None})

    assert len(sent) == 1
    assert sent[0]["task_id"] == "dbt_build"
    assert sent[0]["message"] == "task falhou sem exceção registrada"


def test_alert_failure_without_run_id_or_logical_date(alerts_file):
    ti = SimpleNamespace(dag_id="elt_tlc", task_id="dbt_build")

    alerting.alert_failure({"task_instance": ti, "exception": RuntimeError("boom")})

    (row,) = _read_lines(alerts_file)
    assert set(row) == FIELDS
    assert row["run_id"] is None
    assert row["logical_date"] is None
    assert row["message"] == "boom"
    assert row["details"] == {"try_number": None, "max_tries": None, "log_url": None}


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_notify_webhook_posts_json_with_timeout(monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "http://hook.local/x")
    captured = {}

    def fake_urlopen(req, timeout):
        captured["method"] = req.get_method()
        captured["content_type"] = req.get_header("Content-type")
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(alerting.urllib.request, "urlopen", fake_urlopen)
    entry = {"type": "task_failure", "task_id": "ingest_raw"}

    alerting.notify_webhook(entry)

    assert captured["method"] == "POST"
    assert captured["content_type"] == "application/json"
    assert captured["url"] == "http://hook.local/x"
    assert captured["body"] == entry
    assert captured["timeout"] == 5


def test_notify_webhook_failure_log_hides_url(monkeypatch, caplog):
    secret_url = "http://hook.local/segredo-token-123"
    monkeypatch.setenv("ALERT_WEBHOOK_URL", secret_url)

    def fail(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(alerting.urllib.request, "urlopen", fail)

    with caplog.at_level("WARNING", logger="alerting"):
        alerting.notify_webhook({"type": "x"})

    assert "OSError" in caplog.text
    assert "segredo-token-123" not in caplog.text


def test_emit_never_raises_when_jsonl_write_fails(monkeypatch, caplog):
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)

    def broken(entry, path=None):
        raise PermissionError("sem escrita")

    monkeypatch.setattr(alerting, "write_alert", broken)

    with caplog.at_level("WARNING", logger="alerting"):
        ti = SimpleNamespace(dag_id="elt_tlc", task_id="dbt_build")
        alerting.alert_failure({"task_instance": ti, "exception": None})

    assert "PermissionError" in caplog.text
