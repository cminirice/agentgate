from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agentgate.case import DatasetExport, DatasetValidationError
from agentgate.control_plane import EvaluationService
from agentgate.domain import Case, DatasetPurpose, TargetRef, TargetType
from agentgate.run.targets.base import TargetIntegrationError
from agentgate.storage.sqlite import SQLiteRepository
from agentgate.trace.receivers.otlp_http import (
    decode_content_encoding, encode_otlp_http_protobuf_response,
    ingest_otlp_http_json, ingest_otlp_http_protobuf,
)
from agentgate.trace.models import OtlpIngestionLimits
from agentgate.task import api as task_api

logger = logging.getLogger(__name__)

# 全局数据集服务引用
_datasets_service: Any = None

def get_datasets_service() -> Any:
    """获取数据集服务实例"""
    return _datasets_service

from agentgate.task.repository import TaskRepository
from agentgate.task.service import SchedulerService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def setup_logging(log_dir: str = "logs") -> None:
    """配置日志到指定目录"""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 日志文件路径
    log_file = log_path / "agentgate.log"

    # 配置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    # 单独配置 task 模块的日志级别
    task_logger = logging.getLogger("agentgate.task")
    task_logger.setLevel(logging.INFO)

    scheduler_logger = logging.getLogger("agentgate.task.scheduler")
    scheduler_logger.setLevel(logging.INFO)


class LaunchRequest(BaseModel):
    version: str
    dataset_id: str
    dataset_version: int = Field(ge=1)
    evaluator_ids: list[str] | None = None


class LaunchHttpRequest(BaseModel):
    endpoint: str
    target_id: str
    version_id: str
    credential_ref: str = ""
    platform_id: str = "external"
    dataset_id: str = "loan-risk-policy"
    dataset_version: int = Field(default=1, ge=1)
    evaluator_ids: list[str] | None = None
    timeout_seconds: float = Field(default=30.0, gt=0)


class RerunCaseRequest(BaseModel):
    target_version: str | None = None


class CreateDatasetRequest(BaseModel):
    name: str
    description: str = ""
    purpose: DatasetPurpose = DatasetPurpose.STANDARD


class AddRegressionCaseRequest(BaseModel):
    regression_dataset_id: str | None = None
    new_dataset_name: str | None = None
    new_dataset_description: str = ""
    reason: str = ""


class UpdateDatasetRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    archived: bool | None = None


class CopyDatasetRequest(BaseModel):
    name: str
    source_version: int | None = None


class CreateDraftRequest(BaseModel):
    based_on_version: int | None = None


class ReorderCasesRequest(BaseModel):
    case_ids: list[str]


class ValidateSchemaRequest(BaseModel):
    json_schema: object | str
    instance_mode: Literal["structured", "json_text"] = "structured"


def _raise_dataset_error(exc: ValueError, status_code: int = 422) -> None:
    detail: Any = str(exc)
    if isinstance(exc, DatasetValidationError):
        detail = [item.model_dump(mode="json") for item in exc.issues]
    raise HTTPException(status_code=status_code, detail=detail) from exc


def create_app(database_path: str | Path | None = None) -> FastAPI:
    # 初始化日志配置
    setup_logging()
    logger.info("日志系统初始化完成")

    db_path = database_path or os.getenv("AGENTGATE_DB", "agentgate.db")
    logger.info(f"使用数据库: {db_path}")
    repository = SQLiteRepository(db_path)
    service = EvaluationService(repository)
    datasets = service.dataset_service
    global _datasets_service
    _datasets_service = datasets

    # 初始化任务仓储和服务
    from agentgate.task.repository import Base as TaskBase
    task_engine = create_engine(f"sqlite:///{db_path}")
    TaskBase.metadata.create_all(task_engine)
    TaskSession = sessionmaker(bind=task_engine)
    task_session = TaskSession()
    task_repository = TaskRepository(task_session)
    scheduler_service = SchedulerService(task_repository)
    task_api.set_services(scheduler_service, None)

    # 创建 lifespan 事件处理器
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动时：启动后台调度器（测试用10秒间隔）
        loop = asyncio.get_event_loop()
        loop.create_task(scheduler_service.start_scheduler(interval_seconds=10))
        logger.info("调度器任务已创建")
        yield
        # 关闭时：停止调度器
        scheduler_service.stop_scheduler()

    app = FastAPI(title="AgentGate", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
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
    def list_datasets():
        return service.datasets()

    @api.post("/datasets", status_code=201)
    def create_dataset(request: CreateDatasetRequest):
        try:
            dataset = datasets.create_dataset(
                request.name, request.description, request.purpose,
            )
            draft = datasets.create_draft(dataset.id)
            return {"dataset": dataset, "draft": draft}
        except ValueError as exc:
            _raise_dataset_error(exc)

    @api.get("/datasets/{dataset_id}")
    def dataset_detail(dataset_id: str):
        try:
            return {
                "dataset": datasets.get_dataset(dataset_id),
                "versions": datasets.list_versions(dataset_id),
            }
        except ValueError as exc:
            _raise_dataset_error(exc, 404)

    @api.patch("/datasets/{dataset_id}")
    def update_dataset(dataset_id: str, request: UpdateDatasetRequest):
        try:
            return datasets.update_dataset(
                dataset_id,
                name=request.name,
                description=request.description,
                archived=request.archived,
            )
        except ValueError as exc:
            _raise_dataset_error(exc)

    @api.delete("/datasets/{dataset_id}")
    def archive_dataset(dataset_id: str):
        try:
            return datasets.archive_dataset(dataset_id)
        except ValueError as exc:
            _raise_dataset_error(exc, 404)

    @api.post("/datasets/{dataset_id}/copy", status_code=201)
    def copy_dataset(dataset_id: str, request: CopyDatasetRequest):
        try:
            dataset, draft = datasets.copy_dataset(
                dataset_id, request.name, request.source_version
            )
            return {"dataset": dataset, "draft": draft}
        except ValueError as exc:
            _raise_dataset_error(exc)

    @api.get("/datasets/{dataset_id}/versions")
    def list_dataset_versions(dataset_id: str):
        try:
            return datasets.list_versions(dataset_id)
        except ValueError as exc:
            _raise_dataset_error(exc, 404)

    @api.get("/datasets/{dataset_id}/versions/{version}")
    def dataset_version(dataset_id: str, version: int):
        try:
            return datasets.get_version(dataset_id, version)
        except ValueError as exc:
            _raise_dataset_error(exc, 404)

    @api.get("/datasets/{dataset_id}/drafts/current")
    def current_draft(dataset_id: str):
        try:
            draft = datasets.get_draft(dataset_id)
            if draft is None:
                raise HTTPException(status_code=404, detail="dataset has no active draft")
            return draft
        except ValueError as exc:
            _raise_dataset_error(exc, 404)

    @api.post("/datasets/{dataset_id}/drafts", status_code=201)
    def create_draft(dataset_id: str, request: CreateDraftRequest):
        try:
            return datasets.create_draft(dataset_id, request.based_on_version)
        except ValueError as exc:
            _raise_dataset_error(exc)

    @api.delete("/datasets/{dataset_id}/drafts/current", status_code=204)
    def discard_draft(dataset_id: str):
        try:
            datasets.discard_draft(dataset_id)
        except ValueError as exc:
            _raise_dataset_error(exc, 404)

    @api.post("/datasets/{dataset_id}/drafts/publish")
    def publish_draft(dataset_id: str):
        try:
            return datasets.publish_draft(dataset_id)
        except ValueError as exc:
            _raise_dataset_error(exc)

    @api.post("/datasets/{dataset_id}/drafts/cases", status_code=201)
    def add_case(dataset_id: str, case: Case):
        try:
            return datasets.save_case(dataset_id, case)
        except ValueError as exc:
            _raise_dataset_error(exc)

    @api.put("/datasets/{dataset_id}/drafts/cases/{case_id}")
    def update_case(dataset_id: str, case_id: str, case: Case):
        if case.id != case_id:
            raise HTTPException(status_code=422, detail="Case ID cannot be changed")
        try:
            return datasets.save_case(dataset_id, case)
        except ValueError as exc:
            _raise_dataset_error(exc)

    @api.delete("/datasets/{dataset_id}/drafts/cases/{case_id}")
    def delete_case(dataset_id: str, case_id: str):
        try:
            return datasets.remove_case(dataset_id, case_id)
        except ValueError as exc:
            _raise_dataset_error(exc, 404)

    @api.post("/datasets/{dataset_id}/drafts/cases/{case_id}/copy")
    def copy_case(dataset_id: str, case_id: str):
        try:
            return datasets.copy_case(dataset_id, case_id)
        except ValueError as exc:
            _raise_dataset_error(exc, 404)

    @api.put("/datasets/{dataset_id}/drafts/case-order")
    def reorder_cases(dataset_id: str, request: ReorderCasesRequest):
        try:
            return datasets.reorder_cases(dataset_id, request.case_ids)
        except ValueError as exc:
            _raise_dataset_error(exc)

    @api.get("/datasets/{dataset_id}/versions/{version}/export")
    def export_dataset(dataset_id: str, version: int):
        try:
            return datasets.export_version(dataset_id, version)
        except ValueError as exc:
            _raise_dataset_error(exc, 404)

    @api.post("/datasets/import", status_code=201)
    def import_dataset(payload: DatasetExport):
        try:
            dataset, version = datasets.import_dataset(payload.model_dump(mode="json"))
            return {"dataset": dataset, "version": version}
        except ValueError as exc:
            _raise_dataset_error(exc)

    @api.get("/evaluators")
    def evaluators():
        return service.evaluators()

    @api.post("/json-schema/validate", status_code=200)
    def validate_json_schema(request: ValidateSchemaRequest):
        schema = request.json_schema
        if isinstance(schema, str):
            try:
                schema = json.loads(schema)
            except json.JSONDecodeError as exc:
                return {"valid": False, "errors": [{
                    "code": "input_parse_error",
                    "message": f"JSON 解析失败：{exc.msg}",
                }]}
        return service.validate_json_schema(schema, request.instance_mode)

    @api.get("/runs")
    def runs():
        return repository.list_runs()

    @api.post("/evaluations", status_code=201)
    def launch(request: LaunchRequest):
        try:
            return service.launch(
                request.version,
                request.dataset_id,
                request.dataset_version,
                request.evaluator_ids,
            )
        except (ValueError, TargetIntegrationError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.post("/evaluations/http", status_code=201)
    def launch_http(request: LaunchHttpRequest):
        try:
            return service.launch_http(
                TargetRef(
                    platform_id=request.platform_id,
                    target_type=TargetType.AGENT,
                    external_target_id=request.target_id,
                    external_version_id=request.version_id,
                ),
                endpoint=request.endpoint,
                credential_ref=request.credential_ref or None,
                dataset_id=request.dataset_id,
                dataset_version=request.dataset_version,
                evaluator_ids=request.evaluator_ids,
                timeout_seconds=request.timeout_seconds,
            )
        except (ValueError, TargetIntegrationError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.get("/runs/{run_id}")
    def run_detail(run_id: str):
        report = service.run_detail(run_id)
        if report is None:
            raise HTTPException(status_code=404, detail="run not found")
        return report

    @api.post("/runs/{run_id}/cases/{case_id}/rerun", status_code=201)
    def rerun_case(run_id: str, case_id: str, request: RerunCaseRequest):
        try:
            return service.rerun_case(run_id, case_id, request.target_version)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, TargetIntegrationError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.get("/runs/{run_id}/comparison")
    def rerun_comparison(run_id: str):
        try:
            return service.rerun_comparison(run_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.post("/runs/{run_id}/cases/{case_id}/regression", status_code=201)
    def add_case_to_regression_dataset(
        run_id: str, case_id: str, request: AddRegressionCaseRequest,
    ):
        try:
            dataset, draft, copied = service.add_case_to_regression_dataset(
                run_id=run_id,
                case_id=case_id,
                regression_dataset_id=request.regression_dataset_id,
                new_dataset_name=request.new_dataset_name,
                new_dataset_description=request.new_dataset_description,
                reason=request.reason,
            )
            return {"dataset": dataset, "draft": draft, "case": copied}
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.get("/runs/{run_id}/traces/{case_id}")
    def trace_detail(run_id: str, case_id: str):
        trace = service.trace(run_id, case_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="trace not found")
        return trace

    @app.post("/v1/traces", status_code=200)
    async def receive_otlp(request: Request):
        content_type = request.headers.get("content-type", "")
        body = await request.body()
        limits = OtlpIngestionLimits(
            max_request_bytes=int(os.getenv(
                "AGENTGATE_OTLP_MAX_REQUEST_BYTES", str(4 * 1024 * 1024)
            )),
            max_decompressed_bytes=int(os.getenv(
                "AGENTGATE_OTLP_MAX_DECOMPRESSED_BYTES", str(8 * 1024 * 1024)
            )),
        )
        if len(body) > limits.max_request_bytes:
            raise HTTPException(status_code=413, detail="OTLP request body is too large")
        content_encoding = request.headers.get("content-encoding", "")
        if content_encoding.strip().lower() not in ("", "identity", "gzip"):
            raise HTTPException(status_code=415, detail="unsupported Content-Encoding")
        try:
            body = decode_content_encoding(
                body, content_encoding, limits
            )
            if "application/x-protobuf" in content_type:
                report = ingest_otlp_http_protobuf(body, repository, limits)
                return Response(
                    encode_otlp_http_protobuf_response(report),
                    status_code=200,
                    media_type="application/x-protobuf",
                )
            if "json" not in content_type:
                raise HTTPException(status_code=415, detail="unsupported OTLP content type")
            report = ingest_otlp_http_json(json.loads(body), repository, limits)
        except (OSError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return report

    api.include_router(task_api.router)
    app.include_router(api)
    app.state.repository = repository
    app.state.service = service
    return app


app = create_app()
