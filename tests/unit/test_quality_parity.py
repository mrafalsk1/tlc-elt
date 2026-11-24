"""Paridade entre rules.py (Pandas) e gx_runner.py (Great Expectations) sobre a fixture.

Só roda com Great Expectations instalado (.venv-quality). No venv principal e no CI
é pulado por importorskip. Este é o único teste que importa gx_runner.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("great_expectations")

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from quality import gx_runner, rules


def test_pandas_and_gx_agree_per_expectation():
    trips = pd.read_csv(
        FIXTURES / "trips_sample.csv", parse_dates=[rules.PICKUP, rules.DROPOFF]
    )
    zones = pd.read_csv(FIXTURES / "taxi_zones_sample.csv")

    pandas_res = {r["id"]: r["violations"] for r in rules.validate_frame(trips, zones, "fx")["results"]}
    gx_res = {r["id"]: r["violations"] for r in gx_runner.run_suite(trips, zones, "fx")["results"]}

    assert pandas_res == gx_res
