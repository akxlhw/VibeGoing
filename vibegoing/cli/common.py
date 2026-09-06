"""命令组共用工具：路径解析、标签解析、Soul 展示。"""

from __future__ import annotations

import os
from pathlib import Path

from ..soul import Soul


def home_arg(value: str | None) -> Path:
    return Path(value or os.environ.get("VIBE_HOME", "./.vibe")).expanduser().resolve()


def parse_tags(raw: str | None) -> list[str]:
    """逗号分隔标签解析（principles / capabilities 共用）。"""
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def print_soul(soul: Soul) -> None:
    memory_flag = "开" if soul.memory_enabled else "关"
    runtime = getattr(soul, "runtime", "llm")
    print(f"{soul.emoji} {soul.name}（模型：{soul.model}，执行体：{runtime}，记忆：{memory_flag}）")
    if soul.persona:
        print(f"  人设：{soul.persona}")
    if soul.principles:
        print(f"  原则：{'；'.join(soul.principles)}")
    if soul.capabilities:
        print(f"  能力：{'、'.join(soul.capabilities)}")
