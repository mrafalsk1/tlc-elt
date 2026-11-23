"""Testes de scripts/quality/rules.py (validate_frame). Sem Great Expectations.

Fixtures: tests/fixtures/trips_sample.csv (25 corridas) e taxi_zones_sample.csv.
Linhas sujas conhecidas: 21 (fare nula), 22 (fare 800), 23 (dropoff < pickup),
24 (zona 99), 25 (payment 9). As demais (1-20) são limpas.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from quality import rules


@pytest.fixture
def trips():
    return pd.read_csv(FIXTURES / "trips_sample.csv", parse_dates=[rules.PICKUP, rules.DROPOFF])


@pytest.fixture
def zones():
    return pd.read_csv(FIXTURES / "taxi_zones_sample.csv")


def _by_id(report):
    return {r["id"]: r for r in report["results"]}


def test_fixture_has_25_rows(trips):
    assert len(trips) == 25


def test_detects_each_dirty_rule(trips, zones):
    res = _by_id(rules.validate_frame(trips, zones, "fixture"))
    assert res["fare_not_null"]["violations"] == 1
    assert res["fare_between"]["violations"] == 1
    assert res["dropoff_after_pickup"]["violations"] == 1
    assert res["pickup_zone_fk"]["violations"] == 0
    assert res["dropoff_zone_fk"]["violations"] == 1
    assert res["payment_in_set"]["violations"] == 1


def test_clean_rules_pass(trips, zones):
    res = _by_id(rules.validate_frame(trips, zones, "fixture"))
    assert res["distance_not_null"]["passed"]
    assert res["distance_between"]["passed"]
    assert res["batch_rows_between"]["passed"]


def test_severity_is_declared_per_rule(trips, zones):
    res = _by_id(rules.validate_frame(trips, zones, "fixture"))
    assert res["fare_not_null"]["severity"] == "critical"
    assert res["payment_in_set"]["severity"] == "warning"


def test_empty_batch_fails_row_count(zones):
    empty = pd.DataFrame(columns=[rules.PICKUP, rules.DROPOFF, rules.PU_ZONE, rules.DO_ZONE, rules.FARE, rules.DISTANCE, rules.PAYMENT])
    res = _by_id(rules.validate_frame(empty, zones, "vazio"))
    assert res["batch_rows_between"]["passed"] is False


def test_unknown_expectation_kind_raises(monkeypatch, trips, zones):
    bad = rules.Expectation("x", "fare_amount", "nao_existe", "critical", "x", {})
    monkeypatch.setattr(rules, "EXPECTATIONS", [bad])
    with pytest.raises(ValueError):
        rules.validate_frame(trips, zones, "fixture")


def test_module_does_not_import_great_expectations():
    assert "great_expectations" not in rules.__dict__
