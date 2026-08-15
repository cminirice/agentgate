from pydantic import ValidationError
import pytest

from agentgate.contracts import Case, Dataset, RunSnapshot, TargetSnapshot
from agentgate.evaluator.core import EVALUATORS


def test_run_snapshot_is_immutable():
    snapshot = RunSnapshot(dataset=Dataset(id="d", name="d", version="1", cases=(Case(id="c", name="c", input={}),)),
                           target=TargetSnapshot(name="target", version="v1", provider="deterministic"), evaluators=EVALUATORS)
    with pytest.raises(ValidationError):
        snapshot.target.version = "changed"
