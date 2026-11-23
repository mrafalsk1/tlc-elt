"""Contrato do DAG elt_tlc, verificado por AST (sem importar Airflow)."""

import ast
from pathlib import Path

DAG_FILE = Path(__file__).resolve().parents[2] / "dags" / "elt_tlc.py"


def _tree():
    return ast.parse(DAG_FILE.read_text(encoding="utf-8"))


def _keyword_names(call):
    return {kw.arg for kw in call.keywords}


def _calls_named(tree, name):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    ]


def _default_args_keys(tree):
    keys = set()
    for call in _calls_named(tree, "dag"):
        for kw in call.keywords:
            if kw.arg == "default_args" and isinstance(kw.value, ast.Dict):
                keys |= {k.value for k in kw.value.keys if isinstance(k, ast.Constant)}
    return keys


def test_default_args_have_backoff_and_failure_callback():
    keys = _default_args_keys(_tree())
    assert {"retries", "retry_exponential_backoff", "max_retry_delay", "on_failure_callback"} <= keys


def test_dag_has_sla_miss_callback():
    tree = _tree()
    dag_calls = _calls_named(tree, "dag")
    assert len(dag_calls) == 1
    assert "sla_miss_callback" in _keyword_names(dag_calls[0])


def test_every_bash_task_declares_sla_and_timeout():
    operators = _calls_named(_tree(), "BashOperator")
    assert len(operators) == 3
    for op in operators:
        names = _keyword_names(op)
        assert "sla" in names, "task sem SLA"
        assert "execution_timeout" in names, "task sem execution_timeout"
