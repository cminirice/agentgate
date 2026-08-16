"""OTLP/HTTP JSON receiver boundary."""

from __future__ import annotations

from typing import Any, Protocol

from agentgate.domain import Trace
from agentgate.trace.normalizer import normalize_otlp_json


class TraceSink(Protocol):
    def save_trace(self, trace: Trace) -> None: ...


def ingest_otlp_http_json(payload: dict[str, Any], repository: TraceSink) -> int:
    if not isinstance(payload.get("resourceSpans", []), list):
        raise ValueError("resourceSpans must be an array")
    traces = normalize_otlp_json(payload)
    for trace in traces:
        repository.save_trace(trace)
    return sum(len(trace.spans) for trace in traces)
