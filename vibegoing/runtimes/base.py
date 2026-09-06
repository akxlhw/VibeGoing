"""Runtime 统一抽象（VG-301，PLAN.md §5.3 的落地）。

LLM 与 CLI 执行体收敛到同一接口：上层（TeammateFlow/协作管线）只面对
Runtime，不感知差异——这是"换引擎不换大脑"的架构保证。

并发模型：submit 在后台线程执行，事件经 on_event 实时回调；
wait() 阻塞取最终产出（失败抛 RuntimeError）；cancel() 终止执行。
"""

from __future__ import annotations

import threading
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from crewai.utilities.types import LLMMessage


@dataclass(frozen=True)
class TaskSpec:
    """一次执行请求。CLI Runtime 的 instruction 会作为子进程参数。"""

    instruction: str
    workdir: Path = field(default_factory=Path.cwd)
    timeout_s: float = 600.0


@dataclass
class RuntimeEvent:
    """执行过程事件：stdout=流式输出，status=阶段说明，done/error=终态。"""

    kind: str  # "stdout" | "status" | "done" | "error"
    content: str


@dataclass
class RuntimeHealth:
    ok: bool
    detail: str
    version: str | None = None


class TaskHandle:
    """一次提交的句柄：等待结果、取消执行、回看事件。"""

    def __init__(self, runtime_name: str, task_id: str):
        self.runtime_name = runtime_name
        self.task_id = task_id
        self.events: list[RuntimeEvent] = []
        self._finished = threading.Event()
        self._output: str | None = None
        self._error: str | None = None

    def _complete(self, output: str | None, error: str | None) -> None:
        self._output, self._error = output, error
        self._finished.set()

    def wait(self, timeout: float | None = None) -> str:
        """阻塞到终态；成功返回最终产出，失败抛 RuntimeError。"""
        if not self._finished.wait(timeout):
            raise TimeoutError(f"runtime {self.runtime_name} 未在 {timeout}s 内结束")
        if self._error is not None:
            raise RuntimeError(self._error)
        return self._output or ""

    @property
    def result(self) -> str | None:
        return self._output


class Runtime(ABC):
    """执行体接口：LLM 与 CLI 适配器实现同一契约。"""

    name: str = "runtime"

    @abstractmethod
    def submit(
        self, task: TaskSpec, *, on_event: Callable[[RuntimeEvent], None] | None = None
    ) -> TaskHandle:
        """提交任务，立即返回句柄；事件实时回调。"""

    @abstractmethod
    def health(self) -> RuntimeHealth:
        """可用性检查（CLI 适配器检查二进制是否在 PATH）。"""

    def cancel(self, handle: TaskHandle) -> None:
        """请求取消；默认实现仅标记失败（子类按能力覆写）。"""
        handle._complete(output=None, error="已取消")


class LLMRuntime(Runtime):
    """LLM 执行体：把既有 llm.call 路径收敛到 Runtime 接口（VG-301）。"""

    name = "llm"

    def __init__(self, model: str, llm: Any | None = None):
        if llm is None:
            from ..teammate import _default_llm

            llm = _default_llm(model)
        self.model = model
        self._llm = llm

    def health(self) -> RuntimeHealth:
        return RuntimeHealth(ok=True, detail=f"LiteLLM provider 字符串：{self.model}")

    def submit(
        self, task: TaskSpec, *, on_event: Callable[[RuntimeEvent], None] | None = None
    ) -> TaskHandle:
        handle = TaskHandle(self.name, uuid.uuid4().hex[:8])
        messages: list[LLMMessage] = [{"role": "user", "content": task.instruction}]

        def emit(event: RuntimeEvent) -> None:
            handle.events.append(event)
            if on_event is not None:
                on_event(event)

        def run() -> None:
            try:
                response = self._llm.call(messages=messages)
                content = response if isinstance(response, str) else str(response)
                emit(RuntimeEvent(kind="stdout", content=content))
                emit(RuntimeEvent(kind="done", content=content))
                handle._complete(output=content, error=None)
            except Exception as exc:
                emit(RuntimeEvent(kind="error", content=str(exc)))
                handle._complete(output=None, error=str(exc))

        threading.Thread(target=run, daemon=True).start()
        return handle
