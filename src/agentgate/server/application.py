from __future__ import annotations

import os
from pathlib import Path
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agentgate.control.core import EvaluationService
from agentgate.storage.sqlite import SQLiteRepository
from agentgate.trace.receivers.otlp_http import ingest_otlp_http_json


class LaunchRequest(BaseModel):
    version: str
    dataset_id: str = "loan-risk-policy"
    evaluator_ids: list[str] | None = None


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

    @api.get("/datasets")
    def datasets():
        return service.datasets()

    @api.get("/evaluators")
    def evaluators():
        return service.evaluators()

    @api.get("/runs")
    def runs():
        return repository.list_runs()

    @api.post("/evaluations", status_code=201)
    def launch(request: LaunchRequest):
        try:
            return service.launch(request.version, request.dataset_id, request.evaluator_ids)
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
        try:
            count = ingest_otlp_http_json(await request.json(), repository)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"accepted_spans": count}

    app.include_router(api)
    app.state.repository = repository
    app.state.service = service
    return app


app = create_app()
