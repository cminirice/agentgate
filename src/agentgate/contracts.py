"""Shared immutable contracts for the AgentGate evaluation flow."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    REVIEW = "review"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolArgumentConstraint(Contract):
    tool: str
    path: str
    equals: Any | None = None
    maximum: float | None = None
    minimum: float | None = None


class Case(Contract):
    id: str
    name: str
    input: dict[str, Any]
    initial_state: dict[str, Any] = Field(default_factory=dict)
    expected_state: dict[str, Any] = Field(default_factory=dict)
    required_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    tool_argument_constraints: tuple[ToolArgumentConstraint, ...] = ()
    policy_rules: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


class Dataset(Contract):
    id: str
    name: str
    version: str
    cases: tuple[Case, ...]
    created_at: datetime = Field(default_factory=utcnow)


class TargetSnapshot(Contract):
    name: str
    version: str
    provider: str
    config: dict[str, Any] = Field(default_factory=dict)


class Evaluator(Contract):
    id: str
    name: str
    kind: str
    version: str = "1"
    config: dict[str, Any] = Field(default_factory=dict)


class RunSnapshot(Contract):
    dataset: Dataset
    target: TargetSnapshot
    evaluators: tuple[Evaluator, ...]
    created_at: datetime = Field(default_factory=utcnow)


class Run(Contract):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: RunStatus = RunStatus.PENDING
    snapshot: RunSnapshot
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class SpanKind(StrEnum):
    AGENT = "agent"
    TOOL = "tool"
    STATE = "state"
    EVENT = "event"


class TraceSpan(Contract):
    id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    parent_id: str | None = None
    name: str
    kind: SpanKind
    sequence: int
    started_at: datetime = Field(default_factory=utcnow)
    ended_at: datetime = Field(default_factory=utcnow)
    attributes: dict[str, Any] = Field(default_factory=dict)
    status: str = "ok"


class Trace(Contract):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    case_id: str
    spans: tuple[TraceSpan, ...]
    final_output: dict[str, Any] = Field(default_factory=dict)
    final_state: dict[str, Any] = Field(default_factory=dict)


class Evidence(Contract):
    trace_id: str
    span_ids: tuple[str, ...] = ()
    description: str
    document_refs: tuple[str, ...] = ()


class Result(Contract):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    case_id: str
    evaluator_id: str
    evaluator_name: str
    evaluator_version: str
    verdict: Verdict
    score: float = Field(ge=0, le=1)
    reason: str
    evidence: tuple[Evidence, ...] = ()
    primary_failure_step: str | None = None


class GateDecision(Contract):
    verdict: Verdict
    passed: int
    failed: int
    review: int
    score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    reason: str


class RunReport(Contract):
    run: Run
    results: tuple[Result, ...]
    gate: GateDecision
