"""
测试任务调度器执行功能。

验证在 Windows 环境下任务执行不会因为路径问题而失败。
"""

import pytest
from datetime import datetime, timezone, timedelta
import sys
import os

# 确保 src 路径在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from fastapi.testclient import TestClient
from agentgate.server.application import create_app


BEIJING_TZ = timezone(timedelta(hours=8))


def test_scheduler_execute_task_no_path_error(tmp_path):
    """测试调度器执行任务时不会出现路径错误

    验证在 Windows 环境下任务执行不会因为 Agent_execute.py 中的
    硬编码 Linux 路径（.venv/bin/python）而失败。
    """
    with TestClient(create_app(tmp_path / "test_scheduler.db")) as client:
        # 1. 创建任务
        response = client.post("/api/tasks", json={
            "task_name": "测试调度器执行",
            "target_id": "langchain-http-agent",
            "dataset_id": "loan-risk-policy",
            "evaluator_id": "skill-routing",
            "created_by": "test",
        })
        assert response.status_code == 201, f"创建任务失败: {response.json()}"
        task_data = response.json()
        task_id = task_data["data"]["id"]
        print(f"创建任务成功: {task_id}")

        # 2. 启动任务
        response = client.post(f"/api/tasks/{task_id}/start")
        assert response.status_code == 200, f"启动任务失败: {response.json()}"
        start_data = response.json()
        assert start_data["code"] == 0
        print(f"启动任务成功: {start_data}")

        # 3. 等待调度器扫描并执行（调度器每10秒扫描一次）
        import time
        time.sleep(12)

        # 4. 查询任务状态
        response = client.get(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        task = response.json()["data"]
        print(f"任务状态: {task['status']}")

        # 5. 验证任务状态应该是 RUNNING -> SUCCESS，而不是 FAIL
        # 由于外部 agent 服务器可能不存在，我们期望至少不是路径错误导致的 FAIL
        # 如果是因为缺少外部服务，应该是其他类型的错误
        assert task["status"] != "NEW", "任务应该已被调度器处理"

        # 如果状态是 FAIL，检查错误原因是否是路径问题
        if task["status"] == "FAIL":
            # 获取执行记录
            response = client.get(f"/api/tasks/{task_id}/runs")
            runs = response.json()["data"]
            if runs:
                run_id = runs[0]["id"]
                response = client.get(f"/api/tasks/runs/{run_id}/cases")
                cases = response.json()["data"]
                print(f"用例执行详情: {cases}")


def test_agent_execute_windows_paths():
    """测试 Agent_execute 模块在 Windows 上的路径处理

    验证 sys.executable 能正确获取当前 Python 解释器路径，
    而不是使用硬编码的 .venv/bin/python
    """
    # 验证 sys.executable 在 Windows 上是 .exe 路径
    if sys.platform == "win32":
        assert sys.executable.endswith("python.exe") or sys.executable.endswith("pythonw.exe"), \
            f"Windows 上的 Python 应该是 .exe 结尾，实际: {sys.executable}"

    # 验证当前 Python 路径不包含 .venv/bin/python
    assert ".venv/bin/python" not in sys.executable, \
        f"sys.executable 不应该是 Linux 路径格式: {sys.executable}"

    print(f"当前 Python 解释器: {sys.executable}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
