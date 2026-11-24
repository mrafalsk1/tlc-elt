"""Testes do grafo de zonas (scripts/build_knowledge_graph.py) em grafo pequeno."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from build_knowledge_graph import graph_features  # noqa: E402  (após sys.path, proposital)


def _tiny() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "PULocationID": [1, 2, 1],
            "DOLocationID": [2, 3, 3],
            "trips": [10, 5, 1],
        }
    )


def test_degrees_and_weights():
    features = graph_features(_tiny()).set_index("zone_id")
    assert features.loc[1, "out_degree"] == 2
    assert features.loc[1, "in_degree"] == 0
    assert features.loc[3, "in_degree"] == 2
    assert features.loc[3, "out_degree"] == 0
    assert features.loc[1, "weighted_out_trips"] == 11
    assert features.loc[3, "weighted_in_trips"] == 6


def test_pagerank_sums_to_one():
    features = graph_features(_tiny())
    assert features["pagerank"].sum() == pytest.approx(1.0, abs=1e-6)


def test_betweenness_is_normalized():
    features = graph_features(_tiny())
    assert features["betweenness_centrality"].between(0, 1).all()
    # Nó 2 é o único caminho 1 -> 3: betweenness deve ser o maior do grafo.
    assert features.set_index("zone_id").loc[2, "betweenness_centrality"] == features[
        "betweenness_centrality"
    ].max()


def test_one_row_per_zone():
    features = graph_features(_tiny())
    assert features["zone_id"].is_unique
    assert sorted(features["zone_id"]) == [1, 2, 3]
