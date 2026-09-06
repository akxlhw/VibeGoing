"""Runtime 层：LLM 与 CLI 执行体的统一抽象（M3）。

导入适配器模块以完成注册（claude-code / codex）。
"""

from . import claude_code, codex  # noqa: F401  注册 claude-code / codex runtime
