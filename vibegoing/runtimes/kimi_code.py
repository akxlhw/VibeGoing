"""Kimi Code 适配器（VG-308，月之暗面编码智能体）。

命令契约：`kimi -p <instruction>`（无头单提示，非交互自带权限语义）。

实测修正（2026-09-07，真机）：`-p` 与 `--auto` **互斥**
（`error: Cannot combine --prompt with --auto`）；v0.4.1 基于 --help
的推断有误。外层权限边界由 VibeGoing 的 PermissionGuard 承担。
输出为纯文本（stream-json 契约未稳定，用默认 text）。
"""

from __future__ import annotations

from .base import TaskSpec
from .cli_base import TextLineRuntime
from .registry import register_cli_runtime


class KimiCodeRuntime(TextLineRuntime):
    name = "kimi-code"
    binary = "kimi"

    def build_command(self, task: TaskSpec) -> list[str]:
        return [self.effective_binary, "-p", task.instruction]


register_cli_runtime("kimi-code", KimiCodeRuntime)
