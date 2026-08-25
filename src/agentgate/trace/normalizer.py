"""Normalize OTLP/HTTP JSON into canonical AgentGate Trace objects."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from agentgate.domain import SpanKind, Trace, TraceSpan


def otlp_value(value: dict[str, Any]) -> Any:
    if "stringValue" in value:
        return value["stringValue"]
    if "boolValue" in value:
        return value["boolValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "arrayValue" in value:
        return [otlp_value(item) for item in value["arrayValue"].get("values", [])]
    if "kvlistValue" in value:
        return attributes(value["kvlistValue"].get("values", []))
    return None


def attributes(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {item["key"]: otlp_value(item.get("value", {})) for item in items}


_OPENINFERENCE_KIND_MAP = {
    "LLM": SpanKind.AGENT,
    "AGENT": SpanKind.AGENT,
    "CHAIN": SpanKind.AGENT,
    "TOOL": SpanKind.TOOL,
    "RETRIEVER": SpanKind.TOOL,
    "GUARDRAIL": SpanKind.EVENT,
    "EMBEDDING": SpanKind.EVENT,
    "RERANKER": SpanKind.EVENT,
}


def _resolve_kind(span_attrs: dict[str, Any]) -> SpanKind:
    kind_value = span_attrs.get("agentgate.kind")
    if isinstance(kind_value, str) and kind_value in SpanKind._value2member_map_:
        return SpanKind(kind_value)
    oi_kind = span_attrs.get("openinference.span.kind")
    if isinstance(oi_kind, str):
        mapped = _OPENINFERENCE_KIND_MAP.get(oi_kind.upper())
        if mapped is not None:
            return mapped
    if span_attrs.get("gen_ai.system") is not None:
        return SpanKind.AGENT
    if span_attrs.get("gen_ai.tool.name") is not None or span_attrs.get("tool.name") is not None:
        return SpanKind.TOOL
    return SpanKind.EVENT


def _resolve_run_case(
    span_attrs: dict[str, Any], trace_id: str,
    correlation_resolver: Callable[[str], tuple[str, str] | None] | None,
) -> tuple[str, str]:
    run_id = span_attrs.get("agentgate.run_id")
    case_id = span_attrs.get("agentgate.case_id")
    if isinstance(run_id, str) and isinstance(case_id, str):
        return run_id, case_id
    if correlation_resolver is not None:
        resolved = correlation_resolver(trace_id)
        if resolved is not None:
            return resolved
    return "otlp-external", "external-trace"


def normalize_otlp_json(
    payload: dict[str, Any],
    *,
    correlation_resolver: Callable[[str], tuple[str, str] | None] | None = None,
) -> tuple[Trace, ...]:
    grouped: dict[tuple[str, str, str], list[TraceSpan]] = defaultdict(list)
    for resource_span in payload.get("resourceSpans", []):
        resource_attrs = attributes(
            resource_span.get("resource", {}).get("attributes", [])
        )
        scope_spans = resource_span.get(
            "scopeSpans", resource_span.get("instrumentationLibrarySpans", [])
        )
        for scope_span in scope_spans:
            for raw in scope_span.get("spans", []):
                span_attrs = {
                    **resource_attrs,
                    **attributes(raw.get("attributes", [])),
                }
                trace_id = str(raw.get("traceId") or uuid4().hex)
                run_id, case_id = _resolve_run_case(span_attrs, trace_id, correlation_resolver)
                kind = _resolve_kind(span_attrs)
                sequence = len(grouped[(run_id, case_id, trace_id)])
                grouped[(run_id, case_id, trace_id)].append(TraceSpan(
                    id=str(raw.get("spanId") or uuid4()),
                    trace_id=trace_id,
                    parent_id=raw.get("parentSpanId") or None,
                    name=raw.get("name", "otlp-span"),
                    kind=kind,
                    sequence=sequence,
                    attributes=span_attrs,
                    status=str(raw.get("status", {}).get("code", "ok")).lower(),
                ))
    return tuple(
        Trace(run_id=run_id, case_id=case_id, spans=tuple(spans))
        for (run_id, case_id, _trace_id), spans in grouped.items()
    )
