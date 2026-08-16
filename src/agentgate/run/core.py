from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from agentgate.domain import (
    Case, GateSpec, MetricPlan, Run, RunSnapshot, RunStatus, TargetSnapshot, Trace,
)
from agentgate.evaluator import EVALUATORS, evaluate_case, validate_evaluation_plan
from agentgate.result.service import build_report
from agentgate.storage.base import AgentGateRepository


class Target(Protocol):
    def execute(self, run_id: str, case: Case, version: str) -> Trace: ...


class ExternalSchedulerAdapter(Protocol):
    def execute(self, target: Target, run_id: str, case: Case, version: str) -> Trace: ...


class LocalScheduler:
    def execute(self, target: Target, run_id: str, case: Case, version: str) -> Trace:
        return target.execute(run_id, case, version)


class PythonFunctionTarget:
    def __init__(self, function) -> None:
        self.function = function

    def execute(self, run_id: str, case: Case, version: str) -> Trace:
        return self.function(run_id, case, version)


class RunEngine:
    def __init__(self, repository: AgentGateRepository,
                 scheduler: ExternalSchedulerAdapter | None = None) -> None:
        self.repository = repository
        self.scheduler = scheduler or LocalScheduler()

    def run(self, dataset, target: Target, target_version: str, provider: str = "deterministic",
            evaluators=EVALUATORS) -> Run:
        selected = tuple(evaluators)
        validate_evaluation_plan(dataset, selected)
        snapshot = RunSnapshot(dataset=dataset,
                               target=TargetSnapshot(name="loan-agent", version=target_version, provider=provider),
                               evaluator_specs=selected,
                               primary_evaluator_ids=tuple(item.id for item in selected),
                               metric_plan=MetricPlan(),
                               gate_spec=GateSpec())
        run = Run(snapshot=snapshot, status=RunStatus.RUNNING, started_at=datetime.now(UTC))
        self.repository.save_run(run)
        results = []
        try:
            for case in dataset.cases:
                trace = self.scheduler.execute(target, run.id, case, target_version)
                self.repository.save_trace(trace)
                results.extend(evaluate_case(case, trace, snapshot.evaluator_specs))
            self.repository.save_results(results)
            completed = run.model_copy(update={"status": RunStatus.COMPLETED, "completed_at": datetime.now(UTC)})
            self.repository.save_run(completed)
            return completed
        except Exception as exc:
            failed = run.model_copy(update={"status": RunStatus.FAILED, "completed_at": datetime.now(UTC), "error": str(exc)})
            self.repository.save_run(failed)
            raise

    def report(self, run_id: str):
        run = self.repository.get_run(run_id)
        if run is None:
            return None
        results = self.repository.list_results(run_id)
        return build_report(run, results)
