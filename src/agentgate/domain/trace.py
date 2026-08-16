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


class Trace(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    case_id: str
    spans: tuple[TraceSpan, ...]
    final_output: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    final_state: FrozenJsonObject = Field(default_factory=FrozenJsonObject)

    def completion_sequence(self) -> int:
        return max((span.sequence for span in self.spans), default=-1) + 1
