"""VG-106 召回调优：相关度阈值过滤、同记录去重、注入上限。"""

from __future__ import annotations

from crewai.memory.types import MemoryMatch, MemoryRecord

from vibegoing.soul import Soul
from vibegoing.teammate import TeammateFlow


class StubLLM:
    def call(self, messages, **kwargs):
        return "ok"


class FakeMemory:
    def __init__(self, matches):
        self.matches = matches

    def recall(self, **kwargs):
        return self.matches


def _match(rid: str, content: str, score: float) -> MemoryMatch:
    return MemoryMatch(record=MemoryRecord(id=rid, content=content, scope="/"), score=score)


def _flow(tmp_path, matches, min_score=0.35):
    flow = TeammateFlow(
        soul=Soul(name="ava", memory_enabled=False),
        vibe_home=tmp_path,
        llm=StubLLM(),
        recall_min_score=min_score,
    )
    flow.memory_backend = FakeMemory(matches)
    return flow


def test_recall_filters_low_score(tmp_path):
    flow = _flow(
        tmp_path,
        [
            _match("a", "高相关记忆", 0.9),
            _match("b", "低分噪声", 0.2),
            _match("c", "中等相关", 0.5),
        ],
    )
    assert flow._recall("任意问题") == ["高相关记忆", "中等相关"]


def test_recall_dedupes_and_skips_empty(tmp_path):
    flow = _flow(
        tmp_path,
        [
            _match("a", "记忆一", 0.8),
            _match("a", "记忆一（重复）", 0.7),
            _match("b", "", 0.9),  # 空内容跳过
        ],
    )
    assert flow._recall("问题") == ["记忆一"]


def test_recall_caps_at_three(tmp_path):
    flow = _flow(
        tmp_path,
        [_match(f"r{i}", f"记忆{i}", 0.9) for i in range(5)],
    )
    assert flow._recall("问题") == ["记忆0", "记忆1", "记忆2"]


def test_recall_threshold_default_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBE_RECALL_MIN_SCORE", "0.6")
    flow = TeammateFlow(
        soul=Soul(name="ava", memory_enabled=False),
        vibe_home=tmp_path,
        llm=StubLLM(),
    )
    assert flow.recall_min_score == 0.6
