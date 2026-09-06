"""共享 LLM 工厂：构建 CrewAI LLM 的唯一入口（供各层复用，见 ADR-0001 触点清单）。"""

from __future__ import annotations

from typing import Any


def default_llm(model: str) -> Any:
    from crewai import LLM

    return LLM(model=model)
