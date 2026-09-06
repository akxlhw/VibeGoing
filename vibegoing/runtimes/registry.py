"""Runtime 注册表：按名称取执行体，上层不感知具体实现。"""

from __future__ import annotations

from collections.abc import Callable

from ..soul import Soul
from .base import LLMRuntime, Runtime


def get_runtime(soul: Soul, **kwargs) -> Runtime:
    """按 Soul 的 runtime 绑定构造执行体。

    换引擎 = 改 Soul.runtime 字段；人设、记忆、会话全部不动。
    CLI 适配器（claude-code/codex）由各自模块注册进来。
    """
    name = getattr(soul, "runtime", "llm") or "llm"
    if name == "llm":
        return LLMRuntime(model=soul.model)
    factory = _CLI_FACTORIES.get(name)
    if factory is not None:
        return factory(**kwargs)
    raise ValueError(f"未知 runtime：{name}（可用：{' / '.join(['llm', *_CLI_FACTORIES])}）")


# CLI 适配器注册表（各适配器模块由包 __init__ 导入时自注册）
_CLI_FACTORIES: dict[str, Callable[..., Runtime]] = {}


def register_cli_runtime(name: str, factory: Callable[..., Runtime]) -> None:
    _CLI_FACTORIES[name] = factory


def runtime_names() -> list[str]:
    """全部可用执行体名（llm + 已注册 CLI 适配器），CLI 选项与列表统一取此。

    依赖包 __init__ 已导入全部适配器模块（import 本模块必先经包 __init__）。
    """
    return ["llm", *_CLI_FACTORIES]
