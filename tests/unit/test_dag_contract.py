"""Contrato do DAG elt_tlc, verificado por AST (sem importar Airflow)."""

import ast
from pathlib import Path

DAG_FILE = Path(__file__).resolve().parents[2] / "dags" / "elt_tlc.py"
UNIT_SECONDS = {"hours": 3600, "minutes": 60, "seconds": 1}


def _tree():
    return ast.parse(DAG_FILE.read_text(encoding="utf-8"))


def _calls_named(tree, name):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    ]


def _kwargs(call):
    return {kw.arg: kw.value for kw in call.keywords}


def _duration_seconds(node):
    """Converte pendulum.duration(minutes=30) em segundos, a partir do AST."""
    assert isinstance(node, ast.Call), "duração deve ser pendulum.duration(...)"
    assert ast.unparse(node.func) == "pendulum.duration"
    return sum(
        kw.value.value * UNIT_SECONDS[kw.arg] for kw in node.keywords
    )


def _dag_call():
    (call,) = _calls_named(_tree(), "dag")
    return _kwargs(call)


def _default_args():
    value = _dag_call()["default_args"]
    assert isinstance(value, ast.Dict)
    return {k.value: v for k, v in zip(value.keys, value.values)}


def _bash_tasks():
    tasks = {}
    for op in _calls_named(_tree(), "BashOperator"):
        kwargs = _kwargs(op)
        tasks[kwargs["task_id"].value] = kwargs
    return tasks


def test_default_args_retry_values():
    args = _default_args()
    assert args["retries"].value == 2
    assert args["retry_exponential_backoff"].value is True
    assert _duration_seconds(args["max_retry_delay"]) > 0


def test_on_failure_callback_is_alert_failure():
    args = _default_args()
    assert ast.unparse(args["on_failure_callback"]) == "alerting.alert_failure"


def test_dagrun_timeout_is_three_hours():
    assert _duration_seconds(_dag_call()["dagrun_timeout"]) == 3 * 3600


def test_sla_is_not_used_anywhere():
    tree = _tree()
    assert "sla_miss_callback" not in _dag_call()
    for call in ast.walk(tree):
        if isinstance(call, ast.Call):
            for kw in call.keywords:
                assert kw.arg not in ("sla", "sla_miss_callback"), (
                    f"keyword {kw.arg!r} proibido: sla é relativo ao logical_date (D-10)"
                )


def test_every_task_has_execution_timeout():
    tasks = _bash_tasks()
    assert set(tasks) == {"dbt_source_freshness", "ingest_raw", "dbt_build"}
    expected_minutes = {"dbt_source_freshness": 10, "ingest_raw": 30, "dbt_build": 60}
    for task_id, kwargs in tasks.items():
        seconds = _duration_seconds(kwargs["execution_timeout"])
        assert seconds == expected_minutes[task_id] * 60, task_id
