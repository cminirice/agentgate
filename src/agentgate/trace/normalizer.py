"""Normalize OTLP/HTTP JSON into canonical AgentGate Trace objects."""

from __future__ import annotations

from collections import defaultdict
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


def normalize_otlp_json(payload: dict[str, Any]) -> tuple[Trace, ...]:
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
                run_id = str(span_attrs.get("agentgate.run_id", "otlp-external"))
                case_id = str(span_attrs.get("agentgate.case_id", "external-trace"))
                trace_id = str(raw.get("traceId") or uuid4().hex)
                kind_value = str(span_attrs.get("agentgate.kind", "event"))
                kind = (
                    SpanKind(kind_value)
                    if kind_value in SpanKind._value2member_map_
                    else SpanKind.EVENT
                )
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
