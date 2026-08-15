from __future__ import annotations

from agentgate.demo.loan import LOAN_DATASET, LoanAgent
from agentgate.run.core import RunEngine
from agentgate.storage.base import AgentGateRepository


class EvaluationService:
    """Shared application service used by both CLI and HTTP entry points."""

    def __init__(self, repository: AgentGateRepository) -> None:
        self.repository = repository
        self.engine = RunEngine(repository)

    def launch(self, version: str):
        return self.engine.run(LOAN_DATASET, LoanAgent(self.repository), version)

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
