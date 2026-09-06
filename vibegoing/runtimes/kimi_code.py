"""Kimi Code 适配器（VG-308，月之暗面编码智能体）。

命令契约（本机 `kimi --help` 实测）：`kimi -p <instruction> --auto`
- `-p`：无头单提示模式
- `--auto`：全自主权限（不向用户提问——无头运行的必要条件；
  外层权限边界由 VibeGoing 的 PermissionGuard 承担）
输出为纯文本（stream-json 契约未稳定，v0.4.1 用默认 text）。
"""

from __future__ import annotations

from .base import TaskSpec
from .cli_base import TextLineRuntime
from .registry import register_cli_runtime


class KimiCodeRuntime(TextLineRuntime):
    name = "kimi-code"
    binary = "kimi"

    def build_command(self, task: TaskSpec) -> list[str]:
        return [self.effective_binary, "-p", task.instruction, "--auto"]


register_cli_runtime("kimi-code", KimiCodeRuntime)
