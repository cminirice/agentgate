import pytest
from pydantic import TypeAdapter, ValidationError

from agentgate.domain import (
    Case, CaseTurn, Equals, EvaluatorSpec, RuleEvaluatorSpec, StateExpectation,
    WithinRange,
)


def test_expectation_and_evaluator_discriminated_unions():
    case = Case(
        id="case",
        name="case",
        turns=(CaseTurn(
            id="turn",
            input={"message": "hello"},
            expectations=({"kind": "state", "path": "status",
                           "condition": {"kind": "equals", "expected": "ok"}},),
        ),),
    )
    assert isinstance(case.turns[0].expectations[0], StateExpectation)
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
