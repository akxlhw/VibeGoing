"""ZCode 适配器（VG-307，智谱 Z.AI 编码智能体）。

命令契约：`zcode -p <instruction>`（headless 单提示模式，纯文本输出；
另有 app-server stdio 私有协议，对本项目场景过重，不采用）。

桌面版内置 CLI 通常不在 PATH：设 `VIBE_ZCODE_BIN` 指向二进制即可。
"""

from __future__ import annotations

from .base import TaskSpec
from .cli_base import TextLineRuntime
from .registry import register_cli_runtime


class ZCodeRuntime(TextLineRuntime):
    name = "zcode"
    binary = "zcode"

    def build_command(self, task: TaskSpec) -> list[str]:
        return [self.effective_binary, "-p", task.instruction]


register_cli_runtime("zcode", ZCodeRuntime)
