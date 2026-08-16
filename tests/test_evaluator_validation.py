import pytest

from agentgate.domain import (
    Case, Dataset, Dimension, MatchesJsonSchema, RuleEvaluatorSpec, StateExpectation,
)
from agentgate.evaluator import EVALUATORS, validate_evaluation_plan
from agentgate.evaluator.models import UnsupportedOperator


def test_valid_demo_plan():
    from agentgate.demo.loan import LOAN_DATASET
    validate_evaluation_plan(LOAN_DATASET, EVALUATORS)


def test_json_schema_condition_is_rejected_before_run():
    dataset = Dataset(
        id="schema",
        name="schema",
        version="1",
        cases=(Case(
            id="case",
            name="case",
            input={},
            expectations=(StateExpectation(
                path="value",
                condition=MatchesJsonSchema(json_schema={"type": "string"}),
            ),),
        ),),
    )
    with pytest.raises(UnsupportedOperator):
        validate_evaluation_plan(dataset, EVALUATORS)


def test_one_metric_cannot_map_to_multiple_dimensions():
    dataset = Dataset(id="empty", name="empty", version="1", cases=())
    specs = (
        RuleEvaluatorSpec(
            id="one", name="one", evaluator_type="final_state",
            dimension=Dimension.STATE, metric="same",
        ),
        RuleEvaluatorSpec(
            id="two", name="two", evaluator_type="final_state",
            dimension=Dimension.TOOL_USE, metric="same",
        ),
    )
    with pytest.raises(ValueError, match="cannot belong"):
        validate_evaluation_plan(dataset, specs)
