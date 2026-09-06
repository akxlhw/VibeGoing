"""VG-203 交接协议：报文、序列化与提示词渲染。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vibegoing.collab.handoff import HandoffPacket


def _packet() -> HandoffPacket:
    return HandoffPacket(
        task="汇总调研结论",
        from_agent="researcher",
        to_agent="writer",
        context="用户需要一份给管理层看的摘要",
        prior_outputs=[
            {"source": "researcher/produce", "output": "三条核心发现"},
            {"source": "writer/review", "output": "建议补充风险一节"},
        ],
        expectations="不超过 300 字的摘要",
    )


def test_prompt_contains_all_context():
    prompt = _packet().to_prompt()
    assert "汇总调研结论" in prompt
    assert "researcher" in prompt and "writer" in prompt
    assert "三条核心发现" in prompt and "建议补充风险一节" in prompt
    assert "不超过 300 字" in prompt
    assert "不要重复已完成的工作" in prompt


def test_json_roundtrip():
    packet = _packet()
    restored = HandoffPacket.model_validate_json(packet.model_dump_json())
    assert restored == packet
    assert restored.prior_outputs[0]["source"] == "researcher/produce"


def test_same_agent_rejected():
    with pytest.raises(ValidationError, match="不同的伙伴"):
        HandoffPacket(task="t", from_agent="ava", to_agent="ava")


def test_minimal_packet_prompt_still_works():
    packet = HandoffPacket(task="t", from_agent="a", to_agent="b")
    prompt = packet.to_prompt()
    assert "任务：t" in prompt and "由 a 移交给你（b）" in prompt
