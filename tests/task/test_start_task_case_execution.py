"""
测试任务启动后用例执行明细创建。

通过 TestClient 模拟完整流程：创建任务 -> 启动任务 -> 查询用例执行明细
"""

import pytest
from datetime import datetime, timezone, timedelta

from fastapi.testclient import TestClient
from agentgate.server.application import create_app


BEIJING_TZ = timezone(timedelta(hours=8))


def test_start_task_creates_case_executions(tmp_path):
    """测试启动任务时创建用例执行明细"""
    with TestClient(create_app(tmp_path / "test_start.db")) as client:
        # 1. 创建任务
        response = client.post("/api/tasks", json={
            "task_name": "测试用例执行明细",
            "target_id": "langchain-http-agent",
            "dataset_id": "loan-risk-policy",
            "evaluator_id": "skill-routing",
            "created_by": "test",
        })
        assert response.status_code == 201, f"创建任务失败: {response.json()}"
        task_data = response.json()
        assert task_data["code"] == 0
        task = task_data["data"]
        task_id = task["id"]
        print(f"创建任务成功: {task_id}")

        # 2. 启动任务
        response = client.post(f"/api/tasks/{task_id}/start")
        assert response.status_code == 200, f"启动任务失败: {response.json()}"
        start_data = response.json()
        assert start_data["code"] == 0
        print(f"启动任务成功: {start_data}")

        # 等待一下让异步处理完成
        import time
        time.sleep(0.5)

        # 3. 查询任务的执行记录
        response = client.get(f"/api/tasks/{task_id}/runs")
        assert response.status_code == 200, f"查询执行记录失败: {response.json()}"
        runs_data = response.json()
        assert runs_data["code"] == 0
        runs = runs_data["data"]
        assert len(runs) >= 1, "应该有至少一个执行记录"
        run_id = runs[0]["id"]
        print(f"执行记录ID: {run_id}")

        # 4. 查询用例执行明细
        response = client.get(f"/api/tasks/runs/{run_id}/cases")
        print(f"用例执行明细API响应: {response.json()}")
        assert response.status_code == 200, f"查询用例执行明细失败: {response.json()}"
        cases_data = response.json()
        assert cases_data["code"] == 0
        cases = cases_data["data"]
        print(f"用例执行明细数量: {len(cases)}")

        # 验证用例执行明细不为空
        assert len(cases) > 0, f"用例执行明细列表为空，但应该至少有1条数据！响应: {cases_data}"

        # 验证每条用例执行明细的字段
        for case in cases:
            assert "id" in case, f"用例执行明细缺少id字段: {case}"
            assert "run_id" in case, f"用例执行明细缺少run_id字段: {case}"
            assert "case_id" in case, f"用例执行明细缺少case_id字段: {case}"
            assert "status" in case, f"用例执行明细缺少status字段: {case}"
            assert case["run_id"] == run_id, f"用例执行明细的run_id不匹配: {case['run_id']} != {run_id}"
            print(f"用例执行明细: id={case['id']}, case_id={case['case_id']}, status={case['status']}")


def test_list_run_cases_api(tmp_path):
    """测试用例执行明细API端点"""
    with TestClient(create_app(tmp_path / "test_list.db")) as client:
        # 先创建一个任务并启动
        response = client.post("/api/tasks", json={
            "task_name": "测试列表API",
            "target_id": "langchain-http-agent",
            "dataset_id": "loan-risk-policy",
            "evaluator_id": "skill-routing",
            "created_by": "test",
        })
        task_id = response.json()["data"]["id"]

        # 启动任务
        client.post(f"/api/tasks/{task_id}/start")

        # 等待处理
        import time
        time.sleep(0.5)

        # 获取run_id
        runs_response = client.get(f"/api/tasks/{task_id}/runs")
        runs = runs_response.json()["data"]
        assert len(runs) > 0
        run_id = runs[0]["id"]

        # 测试API路径 - 带 /api/tasks 前缀
        api_path = f"/api/tasks/runs/{run_id}/cases"
        print(f"测试API路径: {api_path}")
        response = client.get(api_path)
        print(f"响应状态: {response.status_code}")
        print(f"响应内容: {response.json()}")

        assert response.status_code == 200, f"API调用失败: {response.text}"
        data = response.json()
        assert data["code"] == 0, f"API返回错误: {data}"
        assert "data" in data, f"API响应缺少data字段: {data}"
        cases = data["data"]
        assert isinstance(cases, list), f"data应该是列表，实际是: {type(cases)}"
        print(f"用例执行明细: {len(cases)} 条")
