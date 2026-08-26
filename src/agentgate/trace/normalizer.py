"""Normalize bounded OTLP/HTTP JSON into transport-independent trace batches."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable
from typing import Any

from agentgate.domain import SpanKind, canonical_json, content_sha256
from agentgate.trace.models import (
    NormalizedSignal, NormalizedSpan, OtlpIngestionLimits, TraceBatch, TraceConflict,
)

_TRACE_ID = re.compile(r"^[0-9a-fA-F]{32}$")
_SPAN_ID = re.compile(r"^[0-9a-fA-F]{16}$")
_ALIASES = {
    "agentgate.run.id": ("agentgate.run_id",),
    "agentgate.case.id": ("agentgate.case_id",),
    "agentgate.turn.id": ("turn_id",),
    "agentgate.span.kind": ("agentgate.kind",),
    "agentgate.final.output": ("agentgate.final_output.json",),
    "agentgate.final.state": ("agentgate.final_state.json",),
    "agentgate.trace.complete": (),
    "agentgate.turn.complete": (),
}
_OPENINFERENCE_KIND_MAP = {
    "LLM": SpanKind.AGENT, "AGENT": SpanKind.AGENT, "CHAIN": SpanKind.AGENT,
    "TOOL": SpanKind.TOOL, "RETRIEVER": SpanKind.TOOL,
    "GUARDRAIL": SpanKind.EVENT, "EMBEDDING": SpanKind.EVENT,
    "RERANKER": SpanKind.EVENT,
}


def _resolve_kind(span_attrs: dict[str, Any]) -> SpanKind:
    explicit = span_attrs.get("agentgate.span.kind")
    if isinstance(explicit, str) and explicit in SpanKind._value2member_map_:
        return SpanKind(explicit)
    oi_kind = span_attrs.get("openinference.span.kind")
    if isinstance(oi_kind, str) and oi_kind.upper() in _OPENINFERENCE_KIND_MAP:
        return _OPENINFERENCE_KIND_MAP[oi_kind.upper()]
    if span_attrs.get("gen_ai.system") is not None:
        return SpanKind.AGENT
    if span_attrs.get("gen_ai.tool.name") is not None or span_attrs.get("tool.name") is not None:
        return SpanKind.TOOL
    return SpanKind.EVENT


def otlp_value(
    value: dict[str, Any], limits: OtlpIngestionLimits | None = None, depth: int = 0
) -> Any:
    limits = limits or OtlpIngestionLimits()
    if depth >= limits.max_anyvalue_depth:
        raise ValueError("AnyValue nesting exceeds configured depth")
    if "stringValue" in value:
        result = value["stringValue"]
        if not isinstance(result, str) or len(result) > limits.max_string_length:
            raise ValueError("OTLP string value is invalid or too long")
        return result
    if "boolValue" in value:
        return value["boolValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "bytesValue" in value:
        raw = value["bytesValue"]
        decoded = base64.b64decode(raw, validate=True)
        if len(decoded) > limits.max_string_length:
            raise ValueError("OTLP bytes value is too large")
        return raw
    if "arrayValue" in value:
        values = value["arrayValue"].get("values", [])
        if len(values) > limits.max_attributes:
            raise ValueError("OTLP array has too many values")
        return [otlp_value(item, limits, depth + 1) for item in values]
    if "kvlistValue" in value:
        return attributes(value["kvlistValue"].get("values", []), limits, depth + 1)
    return None


def attributes(
    items: list[dict[str, Any]], limits: OtlpIngestionLimits | None = None,
    depth: int = 0,
) -> dict[str, Any]:
    limits = limits or OtlpIngestionLimits()
    if not isinstance(items, list) or len(items) > limits.max_attributes:
        raise ValueError("too many OTLP attributes")
    result: dict[str, Any] = {}
    for item in items:
        key = item.get("key")
        if not isinstance(key, str) or not key or len(key) > limits.max_key_length:
            raise ValueError("attribute key is invalid or too long")
        result[key] = otlp_value(item.get("value", {}), limits, depth)
    return result


def _canonicalize(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(raw)
    for canonical, aliases in _ALIASES.items():
        candidates = [
            (key, _compatibility_value(canonical, key, raw[key]))
            for key in (canonical, *aliases) if key in raw
        ]
        if len({canonical_json(value) for _, value in candidates}) > 1:
            raise ValueError(f"conflicting correlation attributes for {canonical}")
        if candidates:
            normalized[canonical] = candidates[0][1]
        for alias in aliases:
            normalized.pop(alias, None)
    return normalized


def _compatibility_value(canonical: str, source_key: str, value: Any) -> Any:
    """Normalize legacy terminal fields emitted by existing Agent SDKs."""
    if canonical in ("agentgate.trace.complete", "agentgate.turn.complete"):
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
    if source_key in ("agentgate.final_output.json", "agentgate.final_state.json"):
        if not isinstance(value, str):
            raise ValueError(f"{source_key} must be a JSON string")
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{source_key} contains invalid JSON") from exc
    return value


def _required_string(attrs: dict[str, Any], key: str) -> str:
    value = attrs.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing or invalid {key}")
    return value


def _optional_string(attrs: dict[str, Any], key: str) -> str | None:
    value = attrs.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid {key}")
    return value


def _bounded_string(value: Any, field: str, limits: OtlpIngestionLimits) -> str:
    if not isinstance(value, str) or len(value) > limits.max_string_length:
        raise ValueError(f"{field} is invalid or too long")
    return value


def _timestamp(raw: dict[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if value in (None, ""):
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{key} cannot be negative")
    return parsed


def _event(raw: dict[str, Any], limits: OtlpIngestionLimits) -> dict[str, Any]:
    return {
        "time_unix_nano": _timestamp(raw, "timeUnixNano"),
        "name": _bounded_string(raw.get("name", ""), "event name", limits),
        "attributes": attributes(raw.get("attributes", []), limits),
        "dropped_attributes_count": int(raw.get("droppedAttributesCount", 0)),
    }


def _link(raw: dict[str, Any], limits: OtlpIngestionLimits) -> dict[str, Any]:
    trace_id = str(raw.get("traceId", "")).lower()
    span_id = str(raw.get("spanId", "")).lower()
    if not _TRACE_ID.fullmatch(trace_id) or not _SPAN_ID.fullmatch(span_id):
        raise ValueError("link contains an invalid traceId or spanId")
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "trace_state": _bounded_string(
            raw.get("traceState", ""), "link traceState", limits
        ),
        "attributes": attributes(raw.get("attributes", []), limits),
        "dropped_attributes_count": int(raw.get("droppedAttributesCount", 0)),
    }


def normalize_otlp_json(
    payload: dict[str, Any], limits: OtlpIngestionLimits | None = None, *,
    correlation_resolver: Callable[
        [str], tuple[str, str] | tuple[str, str, str] | None
    ] | None = None,
) -> TraceBatch:
    limits = limits or OtlpIngestionLimits()
    if not isinstance(payload, dict):
        raise ValueError("OTLP payload must be an object")
    resources = payload.get("resourceSpans", [])
    if not isinstance(resources, list) or len(resources) > limits.max_resources:
        raise ValueError("resourceSpans is invalid or exceeds configured limit")
    spans: list[NormalizedSpan] = []
    signals: list[NormalizedSignal] = []
    conflicts: list[TraceConflict] = []
    errors: list[str] = []
    rejected = 0
    span_index = 0
    for resource_span in resources:
        resource_attrs = attributes(
            resource_span.get("resource", {}).get("attributes", []), limits
        )
        scope_spans = resource_span.get(
            "scopeSpans", resource_span.get("instrumentationLibrarySpans", [])
        )
        if not isinstance(scope_spans, list) or len(scope_spans) > limits.max_scopes_per_resource:
            raise ValueError("scopeSpans is invalid or exceeds configured limit")
        for scope_span in scope_spans:
            scope = scope_span.get("scope", scope_span.get("instrumentationLibrary", {}))
            scope_attrs = attributes(scope.get("attributes", []), limits)
            raw_spans = scope_span.get("spans", [])
            if not isinstance(raw_spans, list):
                raise ValueError("spans must be an array")
            if span_index + len(raw_spans) > limits.max_spans:
                raise ValueError("OTLP request exceeds configured span limit")
            for raw in raw_spans:
                span_index += 1
                raw_attrs: dict[str, Any] = {}
                try:
                    raw_attrs = {
                        **resource_attrs,
                        **scope_attrs,
                        **attributes(raw.get("attributes", []), limits),
                    }
                    span_attrs = _canonicalize(raw_attrs)
                    trace_id = str(raw.get("traceId", "")).lower()
                    span_id = str(raw.get("spanId", "")).lower()
                    parent_id = str(raw.get("parentSpanId", "")).lower() or None
                    if not _TRACE_ID.fullmatch(trace_id):
                        raise ValueError("traceId must be 32 hexadecimal characters")
                    if not _SPAN_ID.fullmatch(span_id):
                        raise ValueError("spanId must be 16 hexadecimal characters")
                    if parent_id is not None and not _SPAN_ID.fullmatch(parent_id):
                        raise ValueError("parentSpanId must be 16 hexadecimal characters")
                    resolved = (
                        correlation_resolver(trace_id)
                        if correlation_resolver is not None else None
                    )
                    if (
                        ("agentgate.run.id" not in span_attrs
                         or "agentgate.case.id" not in span_attrs)
                        and resolved is not None
                    ):
                        span_attrs["agentgate.run.id"] = resolved[0]
                        span_attrs["agentgate.case.id"] = resolved[1]
                        if len(resolved) == 3:
                            span_attrs.setdefault("agentgate.invocation.id", resolved[2])
                    run_id = _required_string(span_attrs, "agentgate.run.id")
                    case_id = _required_string(span_attrs, "agentgate.case.id")
                    start = _timestamp(raw, "startTimeUnixNano")
                    end = _timestamp(raw, "endTimeUnixNano")
                    if start is not None and end is not None and end < start:
                        raise ValueError("span end time cannot precede start time")
                    raw_events = raw.get("events", [])
                    raw_links = raw.get("links", [])
                    if len(raw_events) > limits.max_events or len(raw_links) > limits.max_links:
                        raise ValueError("span events or links exceed configured limit")
                    kind = _resolve_kind(span_attrs)
                    attempt_raw = span_attrs.get("agentgate.invocation.attempt", 0)
                    if isinstance(attempt_raw, bool):
                        raise ValueError("invocation attempt must be an integer")
                    attempt = int(attempt_raw)
                    if attempt < 0:
                        raise ValueError("invocation attempt cannot be negative")
                    if "agentgate.final.state" in span_attrs and not isinstance(
                        span_attrs["agentgate.final.state"], dict
                    ):
                        raise ValueError("agentgate.final.state must be a key-value list")
                    status = raw.get("status", {})
                    normalized = NormalizedSpan(
                        run_id=run_id, case_id=case_id,
                        source_trace_id=trace_id, source_span_id=span_id,
                        parent_span_id=parent_id,
                        turn_id=_optional_string(span_attrs, "agentgate.turn.id"),
                        invocation_id=_optional_string(span_attrs, "agentgate.invocation.id"),
                        invocation_attempt=attempt,
                        name=_bounded_string(
                            raw.get("name") or "otlp-span", "span name", limits
                        ),
                        kind=kind,
                        otel_kind=int(raw["kind"]) if "kind" in raw else None,
                        scope_name=(
                            _bounded_string(scope["name"], "scope name", limits)
                            if "name" in scope else None
                        ),
                        scope_version=(
                            _bounded_string(scope["version"], "scope version", limits)
                            if "version" in scope else None
                        ),
                        start_time_unix_nano=start, end_time_unix_nano=end,
                        attributes=span_attrs,
                        events=tuple(_event(item, limits) for item in raw_events),
                        links=tuple(_link(item, limits) for item in raw_links),
                        dropped_attributes_count=int(raw.get("droppedAttributesCount", 0)),
                        dropped_events_count=int(raw.get("droppedEventsCount", 0)),
                        dropped_links_count=int(raw.get("droppedLinksCount", 0)),
                        status=str(status.get("code", "unset")).lower(),
                        status_message=_bounded_string(
                            status.get("message", ""), "status message", limits
                        ),
                    )
                    spans.append(normalized)
                    signal_values = {
                        "trace_complete": "agentgate.trace.complete",
                        "turn_complete": "agentgate.turn.complete",
                        "final_output": "agentgate.final.output",
                        "final_state": "agentgate.final.state",
                    }
                    for signal_kind, attribute_key in signal_values.items():
                        if attribute_key not in span_attrs:
                            continue
                        value = span_attrs[attribute_key]
                        if signal_kind.endswith("complete") and value is not True:
                            continue
                        signals.append(NormalizedSignal(
                            run_id=run_id, case_id=case_id,
                            source_trace_id=trace_id, source_span_id=span_id,
                            turn_id=normalized.turn_id,
                            invocation_id=normalized.invocation_id,
                            kind=signal_kind, value=value,
                        ))
                except (TypeError, ValueError) as exc:
                    rejected += 1
                    message = f"span {span_index}: {exc}"
                    if len(errors) < 20:
                        errors.append(message)
                    if "conflicting correlation" in str(exc):
                        conflicts.append(TraceConflict(
                            kind="correlation",
                            run_id=raw_attrs.get("agentgate.run.id"),
                            case_id=raw_attrs.get("agentgate.case.id"),
                            source_trace_id=str(raw.get("traceId", "")).lower() or None,
                            source_span_id=str(raw.get("spanId", "")).lower() or None,
                            summary=str(exc)[:500],
                        ))
    normalized_size = len(canonical_json({
        "spans": [item.model_dump(mode="json") for item in spans],
        "signals": [item.model_dump(mode="json") for item in signals],
        "conflicts": [item.model_dump(mode="json") for item in conflicts],
    }).encode("utf-8"))
    if normalized_size > limits.max_normalized_bytes:
        raise ValueError("normalized OTLP request exceeds configured byte limit")
    return TraceBatch(
        content_sha256=content_sha256(payload), spans=tuple(spans),
        signals=tuple(signals), conflicts=tuple(conflicts), errors=tuple(errors),
        rejected_spans=rejected,
    )
