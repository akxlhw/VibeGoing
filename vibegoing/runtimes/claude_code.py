"""Claude Code headless 适配器（VG-302）。

命令契约：`claude -p <instruction> --output-format stream-json`
（工作目录 = TaskSpec.workdir；协议漂移时只改本文件的解析逻辑）。
"""

from __future__ import annotations

import contextlib
import json

from .base import RuntimeEvent, TaskSpec
from .cli_base import CLIRuntimeBase
from .registry import register_cli_runtime


class ClaudeCodeRuntime(CLIRuntimeBase):
    name = "claude-code"
    binary = "claude"

    def build_command(self, task: TaskSpec) -> list[str]:
        return [self.binary, "-p", task.instruction, "--output-format", "stream-json"]

    def parse_line(self, line: str) -> list[RuntimeEvent]:
        if not line.strip():
            return []
        with contextlib.suppress(json.JSONDecodeError):
            data = json.loads(line)
            if not isinstance(data, dict):
                return [RuntimeEvent(kind="stdout", content=line)]
            event_type = data.get("type")
            if event_type == "assistant":
                texts = [
                    block.get("text", "")
                    for block in (data.get("message", {}).get("content", []) or [])
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                text = "".join(t for t in texts if t)
                return [RuntimeEvent(kind="stdout", content=text)] if text else []
            if event_type == "result":
                result = str(data.get("result", ""))
                return [RuntimeEvent(kind="done", content=result)]
            if event_type == "system":
                return [RuntimeEvent(kind="status", content=str(data.get("subtype", "system")))]
            return []
        # 非 JSON 行（版本差异兜底）：按原始输出透传
        return [RuntimeEvent(kind="stdout", content=line)]


register_cli_runtime("claude-code", ClaudeCodeRuntime)
