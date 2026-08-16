from fastapi.testclient import TestClient

from agentgate.server.application import create_app


def test_config_catalogs_and_real_report_metrics(tmp_path):
    with TestClient(create_app(tmp_path / "metrics.db")) as client:
        datasets = client.get("/api/datasets").json()
        evaluators = client.get("/api/evaluators").json()
        assert datasets == [{
            "id": "loan-risk-policy", "name": "高风险贷款策略评估", "version": "1", "case_count": 1,
            "description": "仅评估高风险申请是否正确进入人工复核",
        }]
        assert len(evaluators) == 5
        assert {item["metric"] for item in evaluators} == {"工具准确率", "状态准确率", "策略合规率"}

        response = client.post("/api/evaluations", json={
            "version": "loan-agent-v1-risky", "dataset_id": "loan-risk-policy",
            "evaluator_ids": ["required-tool", "forbidden-tool", "tool-arguments"],
        })
        assert response.status_code == 201
        report = client.get(f"/api/runs/{response.json()['id']}").json()
        assert len(report["results"]) == 3
        metrics = {item["key"]: item for item in report["metrics"]}
        assert metrics["tool_accuracy"] == {
            "key": "tool_accuracy", "label": "工具准确率", "score": 0.0,
            "passed": 0, "total": 3,
        }
        assert metrics["overall_score"]["score"] == 0.0


def test_launch_rejects_empty_evaluator_selection(tmp_path):
    with TestClient(create_app(tmp_path / "invalid.db")) as client:
        response = client.post("/api/evaluations", json={
            "version": "loan-agent-v2-fixed", "dataset_id": "loan-risk-policy", "evaluator_ids": [],
        })
        assert response.status_code == 422
