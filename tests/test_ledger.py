"""VG-205 任务台账：创建、阶段记录、状态机、查询。"""

from __future__ import annotations

import pytest

from vibegoing.collab.ledger import TaskLedger


def test_task_lifecycle_with_stages(tmp_path):
    ledger = TaskLedger(tmp_path / "ledger.db")
    task = ledger.create_task("调研多智能体框架", mode="review")

    assert task.status == "pending"
    ledger.set_status(task.task_id, "running")
    ledger.add_stage(task.task_id, "produce", "researcher", "初稿内容")
    ledger.add_stage(task.task_id, "review", "writer", "复核意见")
    ledger.set_status(task.task_id, "done")

    got = ledger.get(task.task_id)
    assert got is not None
    record, stages = got
    assert record.status == "done"
    assert [(s.stage, s.agent) for s in stages] == [
        ("produce", "researcher"),
        ("review", "writer"),
    ]
    assert stages[0].output == "初稿内容"


def test_get_by_unique_prefix(tmp_path):
    ledger = TaskLedger(tmp_path / "ledger.db")
    task = ledger.create_task("任务A", mode="review")
    got = ledger.get(task.task_id[:4])
    assert got is not None and got[0].task_id == task.task_id

    assert ledger.get("noexist") is None


def test_invalid_status_rejected(tmp_path):
    ledger = TaskLedger(tmp_path / "ledger.db")
    task = ledger.create_task("任务", mode="review")
    with pytest.raises(ValueError, match="非法状态"):
        ledger.set_status(task.task_id, "bogus")
    with pytest.raises(KeyError):
        ledger.set_status("missing-id", "done")


def test_list_orders_by_recent(tmp_path):
    ledger = TaskLedger(tmp_path / "ledger.db")
    first = ledger.create_task("第一个", mode="review")
    second = ledger.create_task("第二个", mode="hierarchy")
    ledger.add_stage(first.task_id, "produce", "a", "x")  # 更新 first 的时间戳

    tasks = ledger.list_tasks()
    assert [t.task_id for t in tasks] == [first.task_id, second.task_id]
    assert tasks[0].mode == "review"
