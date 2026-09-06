"""Codex headless 适配器（VG-303）。

命令契约：`codex exec <instruction>`（纯文本输出；无稳定 JSON 流契约，
按原始行透传）。复用 cli_base 的全部机制，验证抽象可复用。
"""

from __future__ import annotations

from .base import RuntimeEvent, TaskSpec
from .cli_base import CLIRuntimeBase
from .registry import register_cli_runtime


class CodexRuntime(CLIRuntimeBase):
    name = "codex"
    binary = "codex"

    def build_command(self, task: TaskSpec) -> list[str]:
        return [self.binary, "exec", task.instruction]

    def parse_line(self, line: str) -> list[RuntimeEvent]:
        if not line.strip():
            return []
        return [RuntimeEvent(kind="stdout", content=line)]


register_cli_runtime("codex", CodexRuntime)
