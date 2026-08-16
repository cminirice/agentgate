from datetime import UTC, datetime

import pytest

from agentgate.domain import (
    Case, CaseTurn, DatasetVersion, DatasetVersionStatus, Dimension, MatchesJsonSchema,
    RuleEvaluatorSpec, StateExpectation,
)
from agentgate.evaluator import EVALUATORS, validate_evaluation_plan
from agentgate.evaluator.models import UnsupportedOperator


def test_valid_demo_plan():
    from agentgate.demo.loan import LOAN_DATASET_VERSION
    validate_evaluation_plan(LOAN_DATASET_VERSION, EVALUATORS)


def test_json_schema_condition_is_rejected_before_run():
    dataset = DatasetVersion(
        id="schema-v1",
        dataset_id="schema",
        version=1,
        status=DatasetVersionStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        cases=(Case(
            id="case",
            name="case",
            turns=(CaseTurn(
                id="turn",
                input={"value": "x"},
                expectations=(StateExpectation(
                    path="value",
                    condition=MatchesJsonSchema(json_schema={"type": "string"}),
                ),),
            ),),
        ),),
    )
    with pytest.raises(UnsupportedOperator):
        validate_evaluation_plan(dataset, EVALUATORS)


def test_one_metric_cannot_map_to_multiple_dimensions():
    dataset = DatasetVersion(dataset_id="empty", cases=())
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
