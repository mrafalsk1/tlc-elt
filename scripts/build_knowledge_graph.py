#!/usr/bin/env python3
"""Grafo de zonas do TLC: nós = zonas, arestas = viagens pickup → dropoff.

Lê o Parquet cru (PULocationID, DOLocationID), monta o grafo direcionado com peso
= número de viagens e calcula centralidade por zona. Saídas:

  dbt/seeds/zone_graph_features.csv  — 1 linha por zona (entra no `dbt build`)
  data/graph/zone_edges.csv          — edge list, para inspeção e README

Uso: python scripts/build_knowledge_graph.py [--min-trips 1]
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import networkx as nx
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_GLOB = str(REPO_ROOT / "data" / "raw" / "yellow_tripdata_*.parquet")
SEED_PATH = REPO_ROOT / "dbt" / "seeds" / "zone_graph_features.csv"
EDGES_PATH = REPO_ROOT / "data" / "graph" / "zone_edges.csv"

COLUMNS = ["PULocationID", "DOLocationID"]


def load_edges(paths: list[str], min_trips: int = 1) -> pd.DataFrame:
    """Conta viagens por par (pickup, dropoff), descartando nulos."""
    frames = [pd.read_parquet(path, columns=COLUMNS) for path in paths]
    trips = pd.concat(frames, ignore_index=True).dropna()
    edges = (
        trips.groupby(COLUMNS, as_index=False)
        .size()
        .rename(columns={"size": "trips"})
        .astype({"PULocationID": int, "DOLocationID": int})
    )
    return edges[edges["trips"] >= min_trips].reset_index(drop=True)


def build_graph(edges: pd.DataFrame) -> nx.DiGraph:
    graph = nx.DiGraph()
    for row in edges.itertuples(index=False):
        graph.add_edge(int(row.PULocationID), int(row.DOLocationID), weight=int(row.trips))
    return graph


def graph_features(edges: pd.DataFrame) -> pd.DataFrame:
    """Centralidade e grau por zona. Função pura: entra edge list, sai 1 linha por nó."""
    graph = build_graph(edges)
    pagerank = nx.pagerank(graph, alpha=0.85, weight="weight")
    betweenness = nx.betweenness_centrality(graph, normalized=True, weight=None)

    rows = []
    for node in sorted(graph.nodes()):
        rows.append(
            {
                "zone_id": node,
                "in_degree": graph.in_degree(node),
                "out_degree": graph.out_degree(node),
                "weighted_in_trips": sum(d["weight"] for _, _, d in graph.in_edges(node, data=True)),
                "weighted_out_trips": sum(d["weight"] for _, _, d in graph.out_edges(node, data=True)),
                "pagerank": round(pagerank[node], 8),
                "betweenness_centrality": round(betweenness[node], 8),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-trips", type=int, default=1, help="peso mínimo da aresta")
    args = parser.parse_args()

    paths = sorted(glob.glob(RAW_GLOB))
    if not paths:
        print(f"nenhum parquet em {RAW_GLOB}; rode `make seed` primeiro")
        return 1

    edges = load_edges(paths, min_trips=args.min_trips)
    features = graph_features(edges)

    SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    EDGES_PATH.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(SEED_PATH, index=False)
    edges.to_csv(EDGES_PATH, index=False)

    density = nx.density(build_graph(edges))
    print(f"arquivos: {len(paths)}  zonas: {len(features)}  arestas: {len(edges)}")
    print(f"viagens nas arestas: {int(edges['trips'].sum()):,}  densidade: {density:.5f}")
    print(f"seed: {SEED_PATH.relative_to(REPO_ROOT)}  edges: {EDGES_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
