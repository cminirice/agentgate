import json
import sqlite3

import pytest

from agentgate.domain import Case, GateSpec, MetricPlan, Run, RunSnapshot, TargetSnapshot
from agentgate.demo.loan import LOAN_DATASET
from agentgate.evaluator import EVALUATORS
from agentgate.storage.sqlite import SQLiteRepository


def snapshot():
    return RunSnapshot(
        dataset=LOAN_DATASET,
        target=TargetSnapshot(name="loan", version="v1", provider="deterministic"),
        evaluator_specs=EVALUATORS,
        primary_evaluator_ids=tuple(item.id for item in EVALUATORS),
        metric_plan=MetricPlan(),
        gate_spec=GateSpec(),
    )


def test_snapshot_is_deeply_immutable_and_hash_is_stable():
    first = snapshot()
    second = RunSnapshot.model_validate(first.model_dump(mode="json"))
    assert first.snapshot_sha256 == second.snapshot_sha256
    with pytest.raises(TypeError):
        first.dataset.cases[0].input["risk"] = "low"


def test_mutating_source_data_cannot_change_domain_content():
    source = {"nested": [{"risk": "high"}]}
    case = Case(id="case", name="case", input=source)
    source["nested"][0]["risk"] = "low"
    assert case.input["nested"][0]["risk"] == "high"


def test_repository_rejects_tampered_snapshot(tmp_path):
    repository = SQLiteRepository(tmp_path / "tamper.db")
    run = Run(snapshot=snapshot())
    repository.save_run(run)
    with sqlite3.connect(repository.path) as db:
        payload = json.loads(db.execute(
            "SELECT payload FROM runs WHERE id=?", (run.id,)
        ).fetchone()[0])
        payload["snapshot"]["target"]["version"] = "tampered"
        db.execute("UPDATE runs SET payload=? WHERE id=?", (json.dumps(payload), run.id))
    with pytest.raises(ValueError, match="hash mismatch"):
        repository.get_run(run.id)
