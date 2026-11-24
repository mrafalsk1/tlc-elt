"""Testes de scripts/quality/rules.py (validate_frame). Sem Great Expectations.

Fixtures: tests/fixtures/trips_sample.csv (31 corridas) e taxi_zones_sample.csv.
Linhas 1-20: limpas. Sujas:
  21 fare nula | 22 fare 800 | 23 dropoff < pickup | 24 zona de desembarque 99 |
  25 payment 9 (aviso) | 26 distância -1.5 | 27 distância 250 (aviso) |
  28 dropoff == pickup | 29 dropoff nulo (NaT) | 30 zona de embarque nula |
  31 payment nulo (não entra em payment_in_set: nulo é ignorado; ver D-11).
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


def test_fixture_has_31_rows(trips):
    assert len(trips) == 31


def test_exact_violation_counts(trips, zones):
    res = _by_id(rules.validate_frame(trips, zones, "fixture"))
    expected = {
        "fare_not_null": 1,
        "fare_between": 1,
        "distance_not_null": 0,
        "distance_between": 2,
        "dropoff_after_pickup": 3,  # 23 (inversão), 28 (igualdade), 29 (NaT)
        "pickup_zone_not_null": 1,
        "dropoff_zone_not_null": 0,
        "pickup_zone_fk": 0,
        "dropoff_zone_fk": 1,
        "payment_in_set": 1,
        "batch_rows_between": 0,
    }
    assert {k: v["violations"] for k, v in res.items()} == expected


def test_null_fk_is_reported_only_by_not_null(trips, zones):
    res = _by_id(rules.validate_frame(trips, zones, "fixture"))
    assert res["pickup_zone_not_null"]["violations"] == 1
    assert res["pickup_zone_fk"]["violations"] == 0


def test_clean_rows_are_not_flagged(trips, zones):
    res = _by_id(rules.validate_frame(trips, zones, "fixture"))
    assert res["fare_between"]["passed"] is False
    assert res["batch_rows_between"]["passed"]
    assert res["distance_not_null"]["passed"]


def test_severity_is_declared_per_rule(trips, zones):
    res = _by_id(rules.validate_frame(trips, zones, "fixture"))
    assert res["fare_not_null"]["severity"] == "critical"
    assert res["distance_between"]["severity"] == "warning"
    assert res["payment_in_set"]["severity"] == "warning"


def test_empty_batch_fails_row_count(zones):
    empty = pd.DataFrame(
        columns=[
            rules.PICKUP,
            rules.DROPOFF,
            rules.PU_ZONE,
            rules.DO_ZONE,
            rules.FARE,
            rules.DISTANCE,
            rules.PAYMENT,
        ]
    )
    res = _by_id(rules.validate_frame(empty, zones, "vazio"))
    assert res["batch_rows_between"]["passed"] is False


def test_unknown_expectation_kind_raises(monkeypatch, trips, zones):
    bad = rules.Expectation("x", "fare_amount", "nao_existe", "critical", "x", {})
    monkeypatch.setattr(rules, "EXPECTATIONS", [bad])
    with pytest.raises(ValueError):
        rules.validate_frame(trips, zones, "fixture")


def test_module_does_not_import_great_expectations():
    assert "great_expectations" not in rules.__dict__
