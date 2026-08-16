from agentgate.domain import (
    Case, Dimension, Kind, Outcome, RuleEvaluatorSpec, SpanKind, Trace, TraceSpan,
)
from agentgate.evaluator.base import Evaluator
from agentgate.evaluator.models import CheckDraft, Evaluation
from agentgate.evaluator.registry import register_evaluator
from agentgate.evaluator.runner import evaluate_case


@register_evaluator
class CrashingEvaluator(Evaluator):
    kind = Kind.RULE
    evaluator_type = "test_crash"

    def evaluate(self, spec, case, trace, resolve):
        raise RuntimeError("provider token=secret-value")


@register_evaluator
class TimeoutEvaluator(Evaluator):
    kind = Kind.RULE
    evaluator_type = "test_timeout"

    def evaluate(self, spec, case, trace, resolve):
        raise TimeoutError("too slow")


@register_evaluator
class MalformedEvaluator(Evaluator):
    kind = Kind.RULE
    evaluator_type = "test_malformed"

    def evaluate(self, spec, case, trace, resolve):
        return {"not": "an Evaluation"}


@register_evaluator
class HealthyEvaluator(Evaluator):
    kind = Kind.RULE
    evaluator_type = "test_healthy"

    def evaluate(self, spec, case, trace, resolve):
        return Evaluation(checks=())


def spec(evaluator_type):
    return RuleEvaluatorSpec(
        id=evaluator_type,
        name=evaluator_type,
        dimension=Dimension.STATE,
        metric=evaluator_type,
        evaluator_type=evaluator_type,
    )


def test_evaluator_errors_are_results_and_are_sanitized():
    case = Case(id="case", name="case", input={})
    trace = Trace(run_id="run", case_id="case", spans=())
    results = evaluate_case(
        case, trace, (spec("test_crash"), spec("test_timeout"), spec("test_malformed"))
    )
    assert [item.outcome for item in results] == [Outcome.ERROR] * 3
    assert [item.error_evidence.category for item in results] == [
        "crash", "timeout", "invalid_output",
    ]
    assert all(item.score is None and item.primary_failure_step is None for item in results)
    assert "secret-value" not in results[0].error_evidence.message


def test_independent_evaluator_continues_after_error():
    case = Case(id="case", name="case", input={})
    trace = Trace(run_id="run", case_id="case", spans=())
    results = evaluate_case(case, trace, (spec("test_crash"), spec("test_healthy")))
    assert results[0].outcome == Outcome.ERROR
    assert results[1].outcome == Outcome.NOT_APPLICABLE
