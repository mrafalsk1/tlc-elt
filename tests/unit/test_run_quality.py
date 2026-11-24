"""Testes de scripts/quality/run_quality.py com engine fake (sem Great Expectations)."""

import json
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from quality import run_quality


class FakeEngine:
    def __init__(self, results, rows=5):
        self.results = results
        self.rows = rows
        self.calls = 0

    def run_suite(self, df, zones, batch_key):
        self.calls += 1
        return {"batch_key": batch_key, "rows": self.rows, "results": self.results}


def _res(id_, severity, violations):
    return {
        "id": id_,
        "severity": severity,
        "message": id_,
        "violations": violations,
        "passed": violations == 0,
    }


@pytest.fixture
def paths(tmp_path):
    return {
        "input": FIXTURES / "trips_sample.csv",
        "zones": FIXTURES / "taxi_zones_sample.csv",
        "out": tmp_path / "alerts.jsonl",
    }


def _lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_exit_1_when_critical_fails(paths):
    engine = FakeEngine([_res("a", "critical", 3), _res("b", "warning", 0)])
    code = run_quality.run(paths["input"], paths["zones"], str(paths["out"]), None, engine)
    assert code == 1


def test_warning_only_exits_0_and_writes_warning_alert(paths):
    engine = FakeEngine([_res("a", "critical", 0), _res("b", "warning", 2)])
    code = run_quality.run(paths["input"], paths["zones"], str(paths["out"]), None, engine)
    assert code == 0
    (alert,) = _lines(paths["out"])
    assert alert["type"] == "data_quality"
    assert alert["severity"] == "warning"
    assert alert["details"]["failed"] == ["b"]


def test_one_aggregated_alert_per_run(paths):
    engine = FakeEngine([_res("a", "critical", 1), _res("b", "critical", 2), _res("c", "warning", 4)])
    run_quality.run(paths["input"], paths["zones"], str(paths["out"]), None, engine)
    alerts = _lines(paths["out"])
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "critical"
    assert alerts[0]["details"]["violations"] == {"a": 1, "b": 2, "c": 4}
    assert alerts[0]["details"]["failed"] == ["a", "b", "c"]


def test_no_alert_when_everything_passes(paths):
    engine = FakeEngine([_res("a", "critical", 0), _res("b", "warning", 0)])
    code = run_quality.run(paths["input"], paths["zones"], str(paths["out"]), None, engine)
    assert code == 0
    assert _lines(paths["out"]) == []


def test_build_alert_returns_none_without_failures():
    report = {"rows": 1, "results": [_res("a", "critical", 0)]}
    assert run_quality.build_alert(report, "x.csv") is None


def test_limit_zero_means_zero_rows(paths):
    trips = run_quality.load_trips(paths["input"], 0)
    assert len(trips) == 0


def test_limit_none_reads_everything(paths):
    trips = run_quality.load_trips(paths["input"], None)
    assert len(trips) == 31


def test_main_reports_missing_great_expectations(monkeypatch, paths, capsys):
    # sys.modules[...] = None faz o import levantar ImportError, como sem GX instalado.
    monkeypatch.setitem(sys.modules, "quality.gx_runner", None)
    code = run_quality.main(
        ["--input", str(paths["input"]), "--zones", str(paths["zones"]), "--out", str(paths["out"])]
    )
    assert code == 2
    assert "requirements-quality.txt" in capsys.readouterr().err
