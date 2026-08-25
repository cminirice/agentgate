"""OTLP/HTTP JSON receiver boundary."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from agentgate.domain import Trace
from agentgate.trace.normalizer import normalize_otlp_json

LOGGER = logging.getLogger(__name__)


class TraceSink(Protocol):
    def save_trace(self, trace: Trace) -> None: ...
    def get_pending_trace(self, trace_id: str): ...


def ingest_otlp_http_json(payload: dict[str, Any], repository: TraceSink) -> int:
    if not isinstance(payload.get("resourceSpans", []), list):
        raise TypeError("resourceSpans must be an array")

    def resolver(trace_id: str) -> tuple[str, str] | None:
        pending = repository.get_pending_trace(trace_id)
        if pending is None:
            return None
        return pending.run_id, pending.case_id

    traces = normalize_otlp_json(payload, correlation_resolver=resolver)
    for trace in traces:
        if trace.run_id == "otlp-external":
            LOGGER.warning("uncorrelated OTLP trace %s ignored", trace.id)
            continue
        repository.save_trace(trace)
    return sum(len(trace.spans) for trace in traces)
