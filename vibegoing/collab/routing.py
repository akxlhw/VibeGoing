"""能力路由（VG-204）：按任务文本与 Soul 能力标签的匹配度挑选伙伴。

刻意采用确定性的关键词打分（可测试、可解释），不引入 LLM 路由；
任务未命中任何标签时退回 Soul 列表原顺序（用户定义的默认队形）。
"""

from __future__ import annotations

from collections.abc import Sequence

from ..soul import Soul


def _score(task: str, soul: Soul) -> int:
    text = task.lower()
    score = 0
    for capability in soul.capabilities:
        if capability and capability.lower() in text:
            score += 2
    if soul.name.lower() in text:
        score += 3
    return score


def rank_souls(task: str, souls: Sequence[Soul]) -> list[Soul]:
    """按匹配度降序；同分保持原顺序（稳定排序）。"""
    return sorted(souls, key=lambda s: _score(task, s), reverse=True)


def pick_pair(task: str, souls: Sequence[Soul]) -> tuple[Soul, Soul] | None:
    """为"产出 + 复核"挑选两位不同伙伴；不足两位返回 None。"""
    ranked = rank_souls(task, list(souls))
    if len(ranked) < 2:
        return None
    return ranked[0], ranked[1]
