"""
测试用例执行明细创建。

验证启动任务时是否为每个 Case 创建 CaseExecution 记录。
"""

import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agentgate.task.repository import TaskRepository, Base as TaskBase
from agentgate.task.domain import TaskRun, TaskStatus, CaseExecution, generate_uuid


@pytest.fixture
def repository(tmp_path):
    """创建测试用 Repository"""
    db_path = tmp_path / "test_case_execution.db"
    engine = create_engine(f"sqlite:///{db_path}")
    TaskBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    return TaskRepository(session)


def test_case_execution_creation(repository):
    """测试为每个 Case 创建 CaseExecution 记录"""
    # 创建任务
    task_id = generate_uuid()

    # 1. 创建 TaskRun
    run = TaskRun(
        task_id=task_id,
        run_no=1,
        status=TaskStatus.PENDING,
        target_snapshot_id=generate_uuid(),
        dataset_snapshot_id=generate_uuid(),
        evaluator_snapshot_id=generate_uuid(),
        total_cases=3,
    )
    repository.create_run(run)

    # 2. 创建 3 个 CaseSnapshot
    case_snapshot_ids = []
    for i in range(3):
        case_snapshot_id = repository.create_case_snapshot(
            case_id=f"case-{i}",
            name=f"Test Case {i}",
            initial_state={"test": True},
            category="positive",
            difficulty="medium",
            tags="test",
            notes="",
        )
        case_snapshot_ids.append(case_snapshot_id)

        # 为每个 Case 创建 2 个 CaseTurnSnapshot
        for j in range(2):
            repository.create_case_turn_snapshot(
                case_snapshot_id=case_snapshot_id,
                case_turn_id=f"case-{i}-turn-{j}",
                input={"user_input": f"hello {j}"},
                expected_skill="test_skill",
                expectations="",
                required_tools="",
                forbidden_tools="",
                policy_rules="",
                notes="",
            )

    # 3. 为每个 Case 创建 CaseExecution
    case_executions = []
    for i, case_snapshot_id in enumerate(case_snapshot_ids):
        case_execution = CaseExecution(
            run_id=run.id,
            case_id=f"case-{i}",
            status=TaskStatus.PENDING,
        )
        repository.create_case_execution(case_execution)
        case_executions.append(case_execution)

    # 4. 验证 CaseExecution 记录
    assert len(case_executions) == 3, "应该创建 3 个 CaseExecution 记录"

    # 5. 查询用例执行明细
    stored_cases = repository.list_case_executions(run.id)
    assert len(stored_cases) == 3, f"应该返回 3 个用例执行明细，实际返回 {len(stored_cases)}"

    # 验证每个 CaseExecution 的状态
    for case in stored_cases:
        assert case["run_id"] == run.id
        assert case["status"] == "PENDING"


def test_case_snapshot_and_turn_creation(repository):
    """测试 CaseSnapshot 和 CaseTurnSnapshot 创建"""
    # 创建 CaseSnapshot
    case_snapshot_id = repository.create_case_snapshot(
        case_id="original-case-id",
        name="Test Case",
        initial_state={"key": "value"},
        category="positive",
        difficulty="hard",
        tags="tag1,tag2",
        notes="test notes",
    )
    assert case_snapshot_id is not None

    # 创建 CaseTurnSnapshot
    turn_snapshot_id = repository.create_case_turn_snapshot(
        case_snapshot_id=case_snapshot_id,
        case_turn_id="original-turn-id",
        input={"user_input": "test input"},
        expected_skill="calculation",
        expectations="expectation1,expectation2",
        required_tools="tool1,tool2",
        forbidden_tools="tool3",
        policy_rules="rule1,rule2",
        notes="turn notes",
    )
    assert turn_snapshot_id is not None

    # 验证能查询到
    case_snapshot = repository.get_case_snapshot(case_snapshot_id)
    assert case_snapshot is not None
    assert case_snapshot["case_id"] == "original-case-id"
    assert case_snapshot["name"] == "Test Case"
    assert case_snapshot["initial_state"]["key"] == "value"

    turn_snapshot = repository.get_case_turn_snapshot(turn_snapshot_id)
    assert turn_snapshot is not None
    assert turn_snapshot["case_turn_id"] == "original-turn-id"
    assert turn_snapshot["input"]["user_input"] == "test input"
