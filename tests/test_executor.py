"""VG-304 重试执行器：失败重试、台账状态机、权限拒绝不重试。"""

from __future__ import annotations

import pytest

from vibegoing.ledger import TaskLedger
from vibegoing.runtimes.base import Runtime, RuntimeHealth, TaskSpec
from vibegoing.runtimes.executor import run_with_retry
from vibegoing.runtimes.guard import GuardDecision, PermissionDenied


class ScriptedRuntime(Runtime):
    """按脚本逐次成功/抛错的假执行体。"""

    name = "scripted"

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.submitted: list[TaskSpec] = []

    def submit(self, task, *, on_event=None):
        import threading
        import uuid

        from vibegoing.runtimes.base import TaskHandle

        self.submitted.append(task)
        outcome = self.outcomes.pop(0)
        handle = TaskHandle(self.name, uuid.uuid4().hex[:8])
        threading.Timer(0.01, lambda: handle._complete(*outcome)).start()
        return handle

    def health(self):
        return RuntimeHealth(ok=True, detail="")


def _ok(text="产出内容"):
    return (text, None)


def _err(msg="超时"):
    return (None, msg)


def test_retry_succeeds_on_second_attempt(tmp_path):
    ledger = TaskLedger(tmp_path / "ledger.db")
    runtime = ScriptedRuntime([_err(), _ok("第二次成功")])

    output, record = run_with_retry(
        TaskSpec(instruction="任务", workdir=tmp_path, timeout_s=5),
        runtime,
        ledger,
        attempts=2,
    )

    assert output == "第二次成功"
    assert record.status == "done"
    _, stages = ledger.get(record.task_id) or (None, [])
    assert [s.stage for s in stages] == ["attempt-1", "attempt-2"]
    assert "超时" in stages[0].output and stages[1].output == "第二次成功"
    assert record.mode == "cli:scripted"


def test_all_attempts_fail_raises_and_marks_failed(tmp_path):
    ledger = TaskLedger(tmp_path / "ledger.db")
    runtime = ScriptedRuntime([_err("失败一"), _err("失败二")])

    with pytest.raises(RuntimeError, match="失败二"):
        run_with_retry(
            TaskSpec(instruction="任务", workdir=tmp_path, timeout_s=5),
            runtime,
            ledger,
            attempts=2,
        )

    record = ledger.list_tasks()[0]
    assert record.status == "failed"
    _, stages = ledger.get(record.task_id) or (None, [])
    assert len(stages) == 2


def test_permission_denied_does_not_retry(tmp_path):
    ledger = TaskLedger(tmp_path / "ledger.db")

    class DeniedRuntime(Runtime):
        name = "denied"
        calls = 0

        def submit(self, task, *, on_event=None):
            DeniedRuntime.calls += 1
            raise PermissionDenied(GuardDecision(approved=False, reason="不在白名单内"))

        def health(self):
            return RuntimeHealth(ok=True, detail="")

    with pytest.raises(PermissionDenied, match="白名单"):
        run_with_retry(
            TaskSpec(instruction="x", workdir=tmp_path), DeniedRuntime(), ledger, attempts=3
        )

    assert DeniedRuntime.calls == 1  # 未重试
    record = ledger.list_tasks()[0]
    assert record.status == "failed"


def test_attempts_validation(tmp_path):
    ledger = TaskLedger(tmp_path / "ledger.db")
    with pytest.raises(ValueError, match="attempts"):
        run_with_retry(
            TaskSpec(instruction="x", workdir=tmp_path), ScriptedRuntime([]), ledger, attempts=0
        )
