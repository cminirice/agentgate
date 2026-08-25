"""Pre-run validation for a DatasetVersion and selected evaluator definitions."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from agentgate.domain import (
    DatasetVersion, HybridEvaluatorSpec, Kind, MatchesJsonSchema, RuleEvaluatorSpec,
)

from .models import (
    DuplicateEvaluatorId, EvaluatorVersionMismatch, InvalidHybridEvaluator,
    MissingEvaluatorDependency,
)
from .observations import condition_operator
from .registry import resolve_evaluator, resolve_operator

_SUPPORTED_DRAFT_MARKER = "2020-12"
_REMOTE_REF_PREFIXES = ("http://", "https://", "file://")


def _find_remote_ref(schema: Any) -> str | None:
    if isinstance(schema, dict):
        for key in ("$ref", "$dynamicRef"):
            ref = schema.get(key)
            if isinstance(ref, str) and ref.startswith(_REMOTE_REF_PREFIXES):
                return ref
        for value in schema.values():
            found = _find_remote_ref(value)
            if found is not None:
                return found
    elif isinstance(schema, list):
        for item in schema:
            found = _find_remote_ref(item)
            if found is not None:
                return found
    return None


def _validate_json_schema_condition(condition: MatchesJsonSchema) -> None:
    schema = condition.json_schema.to_dict()
    declared = schema.get("$schema")
    if isinstance(declared, str) and _SUPPORTED_DRAFT_MARKER not in declared:
        raise ValueError(f"unsupported JSON Schema draft: {declared}")
    remote_ref = _find_remote_ref(schema)
    if remote_ref is not None:
        raise ValueError(f"remote $ref is not supported: {remote_ref}")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(f"invalid JSON Schema: {exc.message}") from exc


def validate_evaluation_plan(dataset: DatasetVersion, evaluators: tuple) -> None:
    by_id = {item.id: item for item in evaluators}
    if len(by_id) != len(evaluators):
        raise DuplicateEvaluatorId("evaluator IDs must be unique")

    metric_dimensions: dict[str, object] = {}
    for spec in evaluators:
        previous = metric_dimensions.setdefault(spec.metric, spec.dimension)
        if previous != spec.dimension:
            raise ValueError(
                f"metric {spec.metric} cannot belong to both {previous} and {spec.dimension}"
            )
        if isinstance(spec, RuleEvaluatorSpec) and spec.operator:
            resolve_operator(spec.operator, spec.operator_version)
        if isinstance(spec, HybridEvaluatorSpec):
            children = []
            for child in spec.children:
                child_spec = by_id.get(child.evaluator_id)
                if child_spec is None:
                    raise MissingEvaluatorDependency(child.evaluator_id)
                if child.version != child_spec.version:
                    raise EvaluatorVersionMismatch(child.evaluator_id)
                children.append(child_spec)
            if any(item.kind == Kind.HYBRID for item in children):
                raise InvalidHybridEvaluator("nested Hybrid is not supported")
            kinds = {item.kind for item in children}
            if not {Kind.RULE, Kind.LLM_JUDGE}.issubset(kinds):
                raise InvalidHybridEvaluator("Hybrid requires Rule and LLM Judge children")
        resolve_evaluator(spec)

    for case in dataset.cases:
        for turn in case.turns:
            for expectation in turn.expectations:
                if isinstance(expectation.condition, MatchesJsonSchema):
                    _validate_json_schema_condition(expectation.condition)
                resolve_operator(condition_operator(expectation.condition), "1")
