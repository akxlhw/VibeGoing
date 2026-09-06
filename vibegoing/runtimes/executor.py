"""带重试的任务执行器（VG-304）：超时/失败重试，每次尝试落台账。

权限拒绝（配置类错误）不重试——重试只对瞬时故障（超时、非零退出）有意义。
"""

from __future__ import annotations

from collections.abc import Callable

from ..collab.ledger import TaskLedger, TaskRecord
from .base import Runtime, RuntimeEvent, TaskHandle, TaskSpec
from .guard import PermissionDenied


def run_with_retry(
    spec: TaskSpec,
    runtime: Runtime,
    ledger: TaskLedger,
    *,
    attempts: int = 2,
    on_event: Callable[[RuntimeEvent], None] | None = None,
) -> tuple[str, TaskRecord]:
    """执行任务，失败/超时最多重试 attempts 次；每次尝试记一阶段。

    返回 (最终产出, 任务记录)；彻底失败时抛出最后一次的异常。
    """
    if attempts < 1:
        raise ValueError("attempts 必须 ≥ 1")

    record = ledger.create_task(spec.instruction, mode=f"cli:{runtime.name}")
    ledger.set_status(record.task_id, "running")

    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            handle: TaskHandle = runtime.submit(spec, on_event=on_event)
            output = handle.wait(timeout=spec.timeout_s + 30)
            ledger.add_stage(record.task_id, f"attempt-{attempt}", runtime.name, output)
            record = ledger.set_status(record.task_id, "done")
            return output, record
        except PermissionDenied:
            # 红线类拒绝不是瞬时故障：立即落账并上抛，不消耗重试
            ledger.add_stage(record.task_id, f"attempt-{attempt}", runtime.name, "权限拒绝，未执行")
            ledger.set_status(record.task_id, "failed")
            raise
        except Exception as exc:
            last_exc = exc
            ledger.add_stage(record.task_id, f"attempt-{attempt}", runtime.name, f"失败：{exc}")
    record = ledger.set_status(record.task_id, "failed")
    assert last_exc is not None
    raise last_exc
