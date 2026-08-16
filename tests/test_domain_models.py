import pytest
from pydantic import TypeAdapter, ValidationError

from agentgate.domain import (
    Case, Dataset, Equals, EvaluatorSpec, RuleEvaluatorSpec, StateExpectation,
    WithinRange,
)


def test_expectation_and_evaluator_discriminated_unions():
    case = Case(
        id="case",
        name="case",
        input={},
        expectations=({"kind": "state", "path": "status",
                       "condition": {"kind": "equals", "expected": "ok"}},),
    )
    assert isinstance(case.expectations[0], StateExpectation)
    spec = TypeAdapter(EvaluatorSpec).validate_python({
        "kind": "rule", "id": "state", "name": "state", "version": "1",
        "dimension": "state", "metric": "state_match",
        "evaluator_type": "final_state",
    })
    assert isinstance(spec, RuleEvaluatorSpec)


def test_range_and_operator_pair_validation():
    with pytest.raises(ValidationError):
        WithinRange()
    with pytest.raises(ValidationError):
        WithinRange(minimum=2, maximum=1)
    with pytest.raises(ValidationError):
        RuleEvaluatorSpec(
            id="x", name="x", dimension="state", metric="x",
            evaluator_type="final_state", operator="equals",
        )
