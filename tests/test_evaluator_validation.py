from datetime import UTC, datetime

import pytest

from agentgate.domain import (
    Case, CaseTurn, DatasetVersion, DatasetVersionStatus, Dimension, MatchesJsonSchema,
    RuleEvaluatorSpec, StateExpectation,
)
from agentgate.evaluator import EVALUATORS, validate_evaluation_plan


def test_valid_demo_plan():
    from agentgate.demo.loan import LOAN_DATASET_VERSION
    validate_evaluation_plan(LOAN_DATASET_VERSION, EVALUATORS)


def _dataset_with(condition):
    return DatasetVersion(
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
                    condition=condition,
                ),),
            ),),
        ),),
    )


def test_valid_json_schema_plan_is_accepted():
    dataset = _dataset_with(MatchesJsonSchema(json_schema={"type": "string"}))
    validate_evaluation_plan(dataset, EVALUATORS)


def test_remote_json_schema_ref_is_rejected():
    dataset = _dataset_with(MatchesJsonSchema(
        json_schema={"$ref": "https://example.com/x.json"},
    ))
    with pytest.raises(ValueError, match="remote"):
        validate_evaluation_plan(dataset, EVALUATORS)


def test_remote_dynamic_ref_is_rejected():
    dataset = _dataset_with(MatchesJsonSchema(
        json_schema={"$dynamicRef": "https://example.com/x.json"},
    ))
    with pytest.raises(ValueError, match="remote"):
        validate_evaluation_plan(dataset, EVALUATORS)


def test_local_ref_does_not_mask_remote_dynamic_ref():
    dataset = _dataset_with(MatchesJsonSchema(json_schema={
        "$ref": "#/$defs/pos",
        "$dynamicRef": "https://example.com/x.json",
        "$defs": {"pos": {"type": "integer"}},
    }))
    with pytest.raises(ValueError, match="remote"):
        validate_evaluation_plan(dataset, EVALUATORS)


def test_invalid_json_schema_is_rejected():
    dataset = _dataset_with(MatchesJsonSchema(
        json_schema={"type": "not_a_real_type"},
    ))
    with pytest.raises(ValueError, match="invalid JSON Schema"):
        validate_evaluation_plan(dataset, EVALUATORS)


def test_unsupported_draft_is_rejected():
    dataset = _dataset_with(MatchesJsonSchema(json_schema={
        "$schema": "http://json-schema.org/draft-07/schema#", "type": "string",
    }))
    with pytest.raises(ValueError, match="unsupported JSON Schema draft"):
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
