"""CLI Runtime 基座：子进程执行、流式读取、超时与取消（VG-302/303 共用）。

进程启动经 spawn 注入（生产 subprocess.Popen / 测试假进程），解析逻辑由
子类的 build_command/parse_line 提供。所有实现执行前必须通过 PermissionGuard。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

from .base import Runtime, RuntimeEvent, RuntimeHealth, TaskHandle, TaskSpec
from .guard import PermissionDenied, PermissionGuard


class ProcessLike(Protocol):
    """与 subprocess.Popen 兼容的最小接口（测试假进程同构）。"""

    stdout: Iterable[str]

    def wait(self, timeout: float | None = None) -> int: ...

    def terminate(self) -> None: ...


SpawnFn = Callable[[list[str], Path], ProcessLike]


def real_spawn(argv: list[str], cwd: Path) -> ProcessLike:
    """生产用进程启动：不经 shell，参数直传（安全边界的一部分）。"""
    proc = subprocess.Popen(
        argv,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc  # type: ignore[return-value]


class CLIRuntimeBase(Runtime):
    """headless CLI 适配器基类。"""

    name = "cli"
    binary = "cli"

    def __init__(
        self,
        spawn: SpawnFn | None = None,
        guard: PermissionGuard | None = None,
    ):
        self._spawn = spawn or real_spawn
        self.guard = guard or PermissionGuard()
        self._active: dict[str, ProcessLike] = {}

    @property
    def effective_binary(self) -> str:
        """实际使用的二进制：环境变量 VIBE_<NAME>_BIN 可覆盖（桌面内置 CLI 不在 PATH 时用）。"""
        env_key = "VIBE_" + self.name.upper().replace("-", "_") + "_BIN"
        return os.environ.get(env_key, self.binary)

    # 子类定制点
    def build_command(self, task: TaskSpec) -> list[str]:
        raise NotImplementedError

    def parse_line(self, line: str) -> list[RuntimeEvent]:
        """把子进程的一行输出翻译为事件；stdout 计入流式输出，
        done（带内容）会作为最终产出。"""
        raise NotImplementedError

    def health(self) -> RuntimeHealth:
        found = shutil.which(self.effective_binary)
        if found is None:
            env_key = "VIBE_" + self.name.upper().replace("-", "_") + "_BIN"
            return RuntimeHealth(
                ok=False,
                detail=f"未在 PATH 找到 `{self.effective_binary}`"
                f"（桌面内置版可设 {env_key} 指向二进制）",
            )
        return RuntimeHealth(ok=True, detail=f"{self.effective_binary} → {found}")

    def submit(
        self, task: TaskSpec, *, on_event: Callable[[RuntimeEvent], None] | None = None
    ) -> TaskHandle:
        decision = self.guard.check(task.instruction, task.workdir)
        if not decision.approved:
            # 红线：拒绝即不启动进程（VG-305）
            raise PermissionDenied(decision)

        handle = TaskHandle(self.name, uuid.uuid4().hex[:8])
        argv = self.build_command(task)

        def emit(event: RuntimeEvent) -> None:
            handle.events.append(event)
            if on_event is not None:
                on_event(event)

        def run() -> None:
            chunks: list[str] = []
            final: str | None = None
            try:
                proc = self._spawn(argv, task.workdir.expanduser().resolve())
                self._active[handle.task_id] = proc
                emit(RuntimeEvent(kind="status", content=f"已启动：{' '.join(argv[:3])}…"))
                deadline = time.monotonic() + task.timeout_s
                for line in proc.stdout:
                    if time.monotonic() > deadline:
                        proc.terminate()
                        raise TimeoutError(
                            f"执行超过 {task.timeout_s}s，已终止（行间检查，见 ADR-0007）"
                        )
                    for event in self.parse_line(line.rstrip("\n")):
                        if event.kind == "done":
                            final = event.content
                        emit(event)
                        if event.kind == "stdout" and event.content:
                            chunks.append(event.content)
                code = proc.wait(timeout=10)
                if code != 0:
                    raise RuntimeError(f"{self.binary} 退出码 {code}")
                output = final if final is not None else "\n".join(chunks)
                emit(RuntimeEvent(kind="done", content=output))
                handle._complete(output=output, error=None)
            except Exception as exc:
                emit(RuntimeEvent(kind="error", content=str(exc)))
                handle._complete(output=None, error=str(exc))
            finally:
                self._active.pop(handle.task_id, None)

        threading.Thread(target=run, daemon=True).start()
        return handle

    def cancel(self, handle: TaskHandle) -> None:
        proc = self._active.get(handle.task_id)
        if proc is not None:
            proc.terminate()
        handle._complete(output=None, error="已取消（进程已终止）")


class TextLineRuntime(CLIRuntimeBase):
    """纯文本输出适配器：逐行透传为 stdout 事件（zcode/kimi-code/codex/dsh 共用）。"""

    def parse_line(self, line: str) -> list[RuntimeEvent]:
        if not line.strip():
            return []
        return [RuntimeEvent(kind="stdout", content=line)]
