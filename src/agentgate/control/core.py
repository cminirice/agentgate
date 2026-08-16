from __future__ import annotations

from agentgate.demo.loan import LOAN_DATASET, LoanAgent
from agentgate.evaluator.core import EVALUATORS
from agentgate.run.core import RunEngine
from agentgate.storage.base import AgentGateRepository


class EvaluationService:
    """Shared application service used by both CLI and HTTP entry points."""

    def __init__(self, repository: AgentGateRepository) -> None:
        self.repository = repository
        self.engine = RunEngine(repository)

    def launch(self, version: str, dataset_id: str = "loan-demo",
               evaluator_ids: list[str] | None = None):
        if dataset_id != LOAN_DATASET.id:
            raise ValueError(f"unknown dataset: {dataset_id}")
        selected = EVALUATORS if evaluator_ids is None else tuple(
            item for item in EVALUATORS if item.id in evaluator_ids
        )
        if not selected:
            raise ValueError("at least one evaluator is required")
        unknown = set(evaluator_ids or ()) - {item.id for item in EVALUATORS}
        if unknown:
            raise ValueError(f"unknown evaluators: {', '.join(sorted(unknown))}")
        return self.engine.run(LOAN_DATASET, LoanAgent(self.repository), version,
                               evaluators=selected)

    def overview(self) -> dict:
        runs = self.repository.list_runs()
        completed = [run for run in runs if run.status == "completed"]
        latest = self.engine.report(runs[0].id) if runs else None
        return {"total_runs": len(runs), "completed_runs": len(completed),
                "case_count": len(LOAN_DATASET.cases), "latest": latest}

    def run_detail(self, run_id: str):
        return self.engine.report(run_id)

    def trace(self, run_id: str, case_id: str):
        return self.repository.get_trace(run_id, case_id)

    def versions(self) -> list[dict[str, str]]:
        return [{"id": version, "label": "风险版本" if version.endswith("risky") else "修复版本"}
                for version in LoanAgent.versions]

    def datasets(self) -> list[dict]:
        return [{"id": LOAN_DATASET.id, "name": LOAN_DATASET.name,
                 "version": LOAN_DATASET.version, "case_count": len(LOAN_DATASET.cases),
                 "description": "贷款审批、还款计划与投诉处理的确定性演示集"}]

    def evaluators(self) -> list[dict]:
        metric_for = {
            "required-tool": "工具准确率", "forbidden-tool": "工具准确率",
            "tool-arguments": "工具准确率", "final-state": "状态准确率",
            "policy-compliance": "策略合规率",
        }
        return [{"id": item.id, "name": item.name, "kind": item.kind,
                 "version": item.version, "metric": metric_for[item.id]}
                for item in EVALUATORS]
