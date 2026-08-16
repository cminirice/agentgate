from __future__ import annotations

from typing import Any
from uuid import uuid4

from agentgate.domain import (
    Case, Dataset, Equals, SpanKind, StateExpectation, ToolArgumentExpectation,
    Trace, TraceSpan,
)
from agentgate.demo.provider import AgentProvider, DeterministicProvider
from agentgate.storage.base import AgentGateRepository


HIGH_RISK_CASE = Case(
    id="high-risk-approval",
    name="高风险申请需要人工复核",
    input={"skill": "loan_approval", "application_id": "A-100",
           "risk": "high", "amount": 80000},
    expected_skill="loan_approval",
    expectations=(
        ToolArgumentExpectation(
            tool="request_human_review", path="human_review",
            condition=Equals(expected=True),
        ),
        StateExpectation(path="status", condition=Equals(expected="pending_review")),
        StateExpectation(path="approved", condition=Equals(expected=False)),
        StateExpectation(path="human_review", condition=Equals(expected=True)),
    ),
    required_tools=("credit_inquiry", "request_human_review"),
    forbidden_tools=("approve_loan",),
    policy_rules=("high_risk_requires_review",),
    tags=("policy", "high-risk"),
)

LOAN_DATASET = Dataset(
    id="loan-risk-policy",
    name="高风险贷款策略评估",
    version="1",
    cases=(HIGH_RISK_CASE,),
)


class LoanAgent:
    versions = ("loan-agent-v1-risky", "loan-agent-v2-fixed")

    def __init__(self, repository: AgentGateRepository, provider: AgentProvider | None = None) -> None:
        self.repository = repository
        self.provider = provider or DeterministicProvider()

    @staticmethod
    def _span(trace_id: str, sequence: int, name: str, kind: SpanKind, **attributes: Any) -> TraceSpan:
        return TraceSpan(trace_id=trace_id, sequence=sequence, name=name, kind=kind, attributes=attributes)

    def execute(self, run_id: str, case: Case, version: str) -> Trace:
        if version not in self.versions:
            raise ValueError(f"unknown target version: {version}")
        trace_id = uuid4().hex
        spans = [
            self._span(
                trace_id, 0, "skill-routing", SpanKind.ROUTING,
                intent=case.input.get("skill"),
                selected_skill=case.input.get("skill"),
                fallback=False,
            ),
            self._span(
                trace_id, 1, "loan_agent", SpanKind.AGENT,
                version=version, skill=case.input.get("skill"),
            ),
        ]
        skill = case.input.get("skill")
        if skill == "loan_approval":
            spans.append(self._span(trace_id, 2, "credit_inquiry", SpanKind.TOOL, application_id=case.input["application_id"], risk=case.input["risk"]))
            action = self.provider.choose_action(case.input, version)
            args = {"application_id": case.input["application_id"], **action["arguments"]}
            spans.append(self._span(trace_id, 3, action["tool"], SpanKind.TOOL, **args))
            state = {"application_id": case.input["application_id"], "risk": case.input["risk"],
                     "status": "approved" if args["approved"] else "pending_review",
                     "approved": args["approved"], "human_review": args["human_review"]}
        elif skill == "repayment_plan":
            months = int(case.input["months"])
            args = {"application_id": case.input["application_id"], "amount": case.input["amount"], "months": months}
            spans.append(self._span(trace_id, 2, "repayment_plan", SpanKind.TOOL, **args))
            state = {"installments": months, "monthly_amount": round(case.input["amount"] / months, 2)}
        elif skill == "complaint":
            args = {"application_id": case.input["application_id"], "message": case.input["message"]}
            spans.append(self._span(trace_id, 2, "complaint", SpanKind.TOOL, **args))
            state = {"status": "open", "message": case.input["message"]}
        elif skill == "credit_inquiry":
            args = {"application_id": case.input["application_id"]}
            spans.append(self._span(trace_id, 2, "credit_inquiry", SpanKind.TOOL, **args))
            state = {"risk": case.input.get("risk", "low")}
        else:
            raise ValueError(f"unsupported skill: {skill}")
        self.repository.put_business_state("loan", str(case.input.get("application_id", case.id)), state)
        spans.append(self._span(trace_id, len(spans), "business_state", SpanKind.STATE, **state))
        return Trace(run_id=run_id, case_id=case.id, spans=tuple(spans), final_output={"message": "处理完成"}, final_state=state)
