"""Vendor-neutral canonical trace models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import Field

from .base import DomainModel, FrozenJsonObject


def utcnow() -> datetime:
    return datetime.now(UTC)


class SpanKind(StrEnum):
    ROUTING = "routing"
    AGENT = "agent"
    TOOL = "tool"
    STATE = "state"
    EVENT = "event"


class TraceSpan(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    parent_id: str | None = None
    name: str
    kind: SpanKind
    sequence: int = Field(ge=0)
    started_at: datetime = Field(default_factory=utcnow)
    ended_at: datetime = Field(default_factory=utcnow)
    attributes: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    status: str = "ok"


class TraceTurn(DomainModel):
    turn_id: str
    input: FrozenJsonObject
    output: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    state: FrozenJsonObject = Field(default_factory=FrozenJsonObject)


class Trace(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    case_id: str
    spans: tuple[TraceSpan, ...]
    turns: tuple[TraceTurn, ...] = ()
    final_output: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    final_state: FrozenJsonObject = Field(default_factory=FrozenJsonObject)

    def completion_sequence(self) -> int:
        return max((span.sequence for span in self.spans), default=-1) + 1

    def for_turn(self, turn_id: str) -> "Trace":
        record = next((item for item in self.turns if item.turn_id == turn_id), None)
        if record is None:
            if len(self.turns) <= 1:
                return self
            raise ValueError(f"trace has no outcome for turn {turn_id}")
        spans = tuple(
            span for span in self.spans if span.attributes.get("turn_id") == turn_id
        )
        return self.model_copy(update={
            "spans": spans,
            "final_output": record.output,
            "final_state": record.state,
        })
