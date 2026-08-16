"""Tool-use Rule evaluators."""

from __future__ import annotations

from agentgate.domain import (
    FailureStage, Kind, MethodRef, Outcome, SpanKind, ToolArgumentExpectation,
)

from ..base import Evaluator
from ..models import CheckDraft, Evaluation, FailureCandidate
from ..observations import condition_operator, observe
from ..registry import register_evaluator, resolve_operator


def _tool_spans(trace):
    return [item for item in trace.spans if item.kind == SpanKind.TOOL]


@register_evaluator
class RequiredToolEvaluator(Evaluator):
    kind = Kind.RULE
    evaluator_type = "required_tool"

    def applies_to(self, spec, case) -> bool:
        return bool(case.required_tools)

    def evaluate(self, spec, case, trace, resolve) -> Evaluation:
        spans = _tool_spans(trace)
        names = [item.name for item in spans]
        method = MethodRef(operator="contains_all", operator_version="1")
        checks = []
        for tool in case.required_tools:
            matching = [item for item in spans if item.name == tool]
            comparison = resolve_operator("contains_all", "1")(names, (tool,))
            passed = comparison.passed
            checks.append(CheckDraft(
                name=f"必需工具：{tool}",
                outcome=Outcome.PASS if passed else Outcome.FAIL,
                score=1.0 if passed else 0.0,
                reason=f"已调用 {tool}" if passed else f"缺少必需工具：{tool}",
                methods=(method,),
                span_ids=tuple(item.id for item in matching),
                failure=None if passed else FailureCandidate(
                    stage=FailureStage.TOOL_SELECTION, at_trace_completion=True
                ),
            ))
        return Evaluation(checks=tuple(checks))


@register_evaluator
class ForbiddenToolEvaluator(Evaluator):
    kind = Kind.RULE
    evaluator_type = "forbidden_tool"

    def applies_to(self, spec, case) -> bool:
        return bool(case.forbidden_tools)

    def evaluate(self, spec, case, trace, resolve) -> Evaluation:
        spans = _tool_spans(trace)
        method = MethodRef(operator="contains_none", operator_version="1")
        checks = []
        for tool in case.forbidden_tools:
            violating = next((item for item in spans if item.name == tool), None)
            comparison = resolve_operator("contains_none", "1")(
                [item.name for item in spans], (tool,)
            )
            passed = comparison.passed
            checks.append(CheckDraft(
                name=f"禁用工具：{tool}",
                outcome=Outcome.PASS if passed else Outcome.FAIL,
                score=1.0 if passed else 0.0,
                reason=f"未调用 {tool}" if passed else f"调用了禁用工具：{tool}",
                methods=(method,),
                span_ids=(violating.id,) if violating else (),
                failure=None if passed else FailureCandidate(
                    stage=FailureStage.TOOL_SELECTION, span_id=violating.id
                ),
            ))
        return Evaluation(checks=tuple(checks))


@register_evaluator
class ToolArgumentsEvaluator(Evaluator):
    kind = Kind.RULE
    evaluator_type = "tool_arguments"

    def applies_to(self, spec, case) -> bool:
        return any(isinstance(item, ToolArgumentExpectation) for item in case.expectations)

    def evaluate(self, spec, case, trace, resolve) -> Evaluation:
        checks = []
        expectations = [
            item for item in case.expectations if isinstance(item, ToolArgumentExpectation)
        ]
        for expectation in expectations:
            observation = observe(trace, expectation)
            operator_name = condition_operator(expectation.condition)
            method = MethodRef(
                operator=operator_name,
                operator_version="1",
                condition_kind=expectation.condition.kind,
            )
            if not observation.values:
                checks.append(CheckDraft(
                    name=expectation.name or f"{expectation.tool}.{expectation.path}",
                    outcome=Outcome.NOT_APPLICABLE,
                    score=None,
                    reason=f"{expectation.tool} 未调用；参数检查不适用",
                    methods=(method,),
                ))
                continue
            operator = resolve_operator(operator_name, "1")
            comparisons = [
                operator(value, expectation.condition) for value in observation.values
            ]
            passed = (
                all(item.passed for item in comparisons)
                if expectation.occurrence == "all"
                else any(item.passed for item in comparisons)
            )
            failing_index = next(
                (index for index, item in enumerate(comparisons) if not item.passed), 0
            )
            span_id = observation.span_ids[failing_index] if observation.span_ids else None
            checks.append(CheckDraft(
                name=expectation.name or f"{expectation.tool}.{expectation.path}",
                outcome=Outcome.PASS if passed else Outcome.FAIL,
                score=1.0 if passed else 0.0,
                reason="工具参数符合预期" if passed else comparisons[failing_index].reason,
                methods=(method,),
                span_ids=tuple(item for item in observation.span_ids if item),
                failure=None if passed else FailureCandidate(
                    stage=FailureStage.TOOL_ARGUMENTS, span_id=span_id
                ),
            ))
        return Evaluation(checks=tuple(checks))
