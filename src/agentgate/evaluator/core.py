from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentgate.contracts import Case, Evaluator, Evidence, Result, SpanKind, Trace, Verdict

EVALUATORS = (
    Evaluator(id="required-tool", name="必需工具", kind="required_tool"),
    Evaluator(id="forbidden-tool", name="禁用工具", kind="forbidden_tool"),
    Evaluator(id="tool-arguments", name="工具参数", kind="tool_arguments"),
    Evaluator(id="final-state", name="最终状态", kind="final_state"),
    Evaluator(id="policy-compliance", name="策略合规", kind="policy_compliance"),
)


def _tool_spans(trace: Trace):
    return [span for span in trace.spans if span.kind == SpanKind.TOOL]


def _value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _result(evaluator: Evaluator, case: Case, trace: Trace, passed: bool, reason: str,
            span_ids: tuple[str, ...] = (), primary_failure_step: str | None = None) -> Result:
    return Result(run_id=trace.run_id, case_id=case.id, evaluator_id=evaluator.id,
                  evaluator_name=evaluator.name, evaluator_version=evaluator.version,
                  verdict=Verdict.PASS if passed else Verdict.FAIL, score=1.0 if passed else 0.0,
                  reason=reason,
                  evidence=(Evidence(trace_id=trace.id, span_ids=span_ids, description=reason),),
                  primary_failure_step=None if passed else primary_failure_step)


def required_tool(evaluator: Evaluator, case: Case, trace: Trace) -> Result:
    spans = _tool_spans(trace); names = {span.name for span in spans}
    missing = [name for name in case.required_tools if name not in names]
    return _result(evaluator, case, trace, not missing,
                   "所有必需工具均已调用" if not missing else f"缺少必需工具：{', '.join(missing)}",
                   tuple(span.id for span in spans), missing[0] if missing else None)


def forbidden_tool(evaluator: Evaluator, case: Case, trace: Trace) -> Result:
    violating = [span for span in _tool_spans(trace) if span.name in case.forbidden_tools]
    return _result(evaluator, case, trace, not violating,
                   "未调用禁用工具" if not violating else f"调用了禁用工具：{violating[0].name}",
                   tuple(span.id for span in violating), violating[0].name if violating else None)


def tool_arguments(evaluator: Evaluator, case: Case, trace: Trace) -> Result:
    problems: list[str] = []; relevant = []
    for constraint in case.tool_argument_constraints:
        span = next((item for item in _tool_spans(trace) if item.name == constraint.tool), None)
        if span is None:
            problems.append(f"{constraint.tool} 未调用"); continue
        relevant.append(span); actual = _value(span.attributes, constraint.path)
        if constraint.equals is not None and actual != constraint.equals:
            problems.append(f"{constraint.tool}.{constraint.path} 应为 {constraint.equals}")
        if constraint.maximum is not None and (not isinstance(actual, (int, float)) or actual > constraint.maximum):
            problems.append(f"{constraint.tool}.{constraint.path} 超过上限 {constraint.maximum}")
        if constraint.minimum is not None and (not isinstance(actual, (int, float)) or actual < constraint.minimum):
            problems.append(f"{constraint.tool}.{constraint.path} 低于下限 {constraint.minimum}")
    fallback = case.tool_argument_constraints[0].tool if case.tool_argument_constraints else None
    return _result(evaluator, case, trace, not problems,
                   "工具参数符合约束" if not problems else "；".join(problems),
                   tuple(span.id for span in relevant),
                   (relevant[0].name if relevant else fallback) if problems else None)


def final_state(evaluator: Evaluator, case: Case, trace: Trace) -> Result:
    problems = [f"{key} 应为 {expected}" for key, expected in case.expected_state.items()
                if trace.final_state.get(key) != expected]
    state_span = next((span for span in trace.spans if span.kind == SpanKind.STATE), None)
    return _result(evaluator, case, trace, not problems,
                   "最终状态符合预期" if not problems else "；".join(problems),
                   (state_span.id,) if state_span else (), "business_state" if problems else None)


def policy_compliance(evaluator: Evaluator, case: Case, trace: Trace) -> Result:
    problems: list[str] = []; violation_span = None
    if "high_risk_requires_review" in case.policy_rules and case.input.get("risk") == "high":
        violation_span = next((span for span in _tool_spans(trace) if span.name == "approve_loan"), None)
        if violation_span or trace.final_state.get("human_review") is not True:
            problems.append("高风险申请必须进入人工复核且不得直接批准")
    return _result(evaluator, case, trace, not problems,
                   "策略规则均满足" if not problems else "；".join(problems),
                   (violation_span.id,) if violation_span else (),
                   violation_span.name if violation_span else ("business_state" if problems else None))


FUNCTIONS: dict[str, Callable[[Evaluator, Case, Trace], Result]] = {
    "required_tool": required_tool, "forbidden_tool": forbidden_tool,
    "tool_arguments": tool_arguments, "final_state": final_state,
    "policy_compliance": policy_compliance,
}


def evaluate_case(case: Case, trace: Trace, evaluators: tuple[Evaluator, ...] = EVALUATORS) -> list[Result]:
    return [FUNCTIONS[item.kind](item, case, trace) for item in evaluators]
