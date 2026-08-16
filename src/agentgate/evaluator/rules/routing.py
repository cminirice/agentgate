"""Routing-dimension Rule evaluator."""

from __future__ import annotations

from agentgate.domain import Equals, FailureStage, Kind, MethodRef, Outcome, SpanKind

from ..base import Evaluator
from ..models import CheckDraft, Evaluation, FailureCandidate
from ..registry import register_evaluator, resolve_operator


@register_evaluator
class SkillRoutingEvaluator(Evaluator):
    kind = Kind.RULE
    evaluator_type = "skill_routing"

    def applies_to(self, spec, case) -> bool:
        return case.expected_skill is not None

    def evaluate(self, spec, case, trace, resolve) -> Evaluation:
        span = next((item for item in trace.spans if item.kind == SpanKind.ROUTING), None)
        method = MethodRef(operator="equals", operator_version="1")
        if span is None:
            return Evaluation(checks=(CheckDraft(
                name="技能路由",
                outcome=Outcome.FAIL,
                score=0.0,
                reason="未产生路由决策",
                methods=(method,),
                failure=FailureCandidate(stage=FailureStage.ROUTING, at_trace_completion=True),
            ),))
        selected = span.attributes.get("selected_skill")
        comparison = resolve_operator("equals", "1")(
            selected, Equals(expected=case.expected_skill)
        )
        passed = comparison.passed
        return Evaluation(checks=(CheckDraft(
            name="技能路由",
            outcome=Outcome.PASS if passed else Outcome.FAIL,
            score=1.0 if passed else 0.0,
            reason="路由正确" if passed else f"预期 {case.expected_skill}，实际 {selected}",
            methods=(method,),
            span_ids=(span.id,),
            failure=None if passed else FailureCandidate(stage=FailureStage.ROUTING, span_id=span.id),
        ),))
