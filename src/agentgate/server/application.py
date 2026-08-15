from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agentgate.contracts import SpanKind, Trace, TraceSpan
from agentgate.control.core import EvaluationService
from agentgate.storage.sqlite import SQLiteRepository


class LaunchRequest(BaseModel):
    version: str


def _otlp_value(value: dict[str, Any]) -> Any:
    for key in ("stringValue", "boolValue", "intValue", "doubleValue", "arrayValue", "kvlistValue"):
        if key in value:
            return value[key]
    return None


def _attributes(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {item["key"]: _otlp_value(item.get("value", {})) for item in items}


def _ingest_otlp(payload: dict[str, Any], repository: SQLiteRepository) -> int:
    grouped: dict[tuple[str, str, str], list[TraceSpan]] = {}
    for resource_span in payload.get("resourceSpans", []):
        resource_attrs = _attributes(resource_span.get("resource", {}).get("attributes", []))
        for scope_span in resource_span.get("scopeSpans", resource_span.get("instrumentationLibrarySpans", [])):
            for sequence, raw in enumerate(scope_span.get("spans", [])):
                attrs = {**resource_attrs, **_attributes(raw.get("attributes", []))}
                run_id = str(attrs.get("agentgate.run_id", "otlp-external"))
                case_id = str(attrs.get("agentgate.case_id", "external-trace"))
                trace_id = raw.get("traceId") or uuid4().hex
                kind_value = str(attrs.get("agentgate.kind", "event"))
                kind = SpanKind(kind_value) if kind_value in SpanKind._value2member_map_ else SpanKind.EVENT
                span = TraceSpan(id=raw.get("spanId") or str(uuid4()), trace_id=trace_id,
                                 parent_id=raw.get("parentSpanId") or None,
                                 name=raw.get("name", "otlp-span"), kind=kind,
                                 sequence=sequence, attributes=attrs)
                grouped.setdefault((run_id, case_id, trace_id), []).append(span)
    for (run_id, case_id, _trace_id), spans in grouped.items():
        repository.save_trace(Trace(run_id=run_id, case_id=case_id, spans=tuple(spans)))
    return sum(map(len, grouped.values()))


def create_app(database_path: str | Path | None = None) -> FastAPI:
    repository = SQLiteRepository(database_path or os.getenv("AGENTGATE_DB", "agentgate.db"))
    service = EvaluationService(repository)
    app = FastAPI(title="AgentGate", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])
    api = APIRouter(prefix="/api")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/overview")
    def overview():
        return service.overview()

    @api.get("/versions")
    def versions():
        return service.versions()

    @api.get("/runs")
    def runs():
        return repository.list_runs()

    @api.post("/evaluations", status_code=201)
    def launch(request: LaunchRequest):
        try:
            return service.launch(request.version)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.get("/runs/{run_id}")
    def run_detail(run_id: str):
        report = service.run_detail(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="run not found")
        return report

    @api.get("/runs/{run_id}/traces/{case_id}")
    def trace_detail(run_id: str, case_id: str):
        trace = service.trace(run_id, case_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="trace not found")
        return trace

    @app.post("/v1/traces", status_code=202)
    async def receive_otlp(request: Request):
        content_type = request.headers.get("content-type", "")
        if "json" not in content_type:
            raise HTTPException(status_code=415, detail="P1 receiver accepts OTLP/HTTP JSON")
        count = _ingest_otlp(await request.json(), repository)
        return {"accepted_spans": count}

    app.include_router(api)
    app.state.repository = repository
    app.state.service = service
    return app


app = create_app()
