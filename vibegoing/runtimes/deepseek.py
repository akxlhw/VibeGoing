"""DeepSeek Harness 适配器（VG-309）。

命令契约（官方 CLI README）：`dsh --profile headless "<job>"`
- 单次全新会话，打印最终答案后退出；失败退出码非零
- 工作目录 = 调用目录（适配器的 spawn cwd 即工作区根）
纯文本输出。
"""

from __future__ import annotations

from .base import TaskSpec
from .cli_base import TextLineRuntime
from .registry import register_cli_runtime


class DeepSeekHarnessRuntime(TextLineRuntime):
    name = "deepseek-harness"
    binary = "dsh"

    def build_command(self, task: TaskSpec) -> list[str]:
        return [self.effective_binary, "--profile", "headless", task.instruction]


register_cli_runtime("deepseek-harness", DeepSeekHarnessRuntime)
