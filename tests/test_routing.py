"""VG-204 能力路由与 Soul.capabilities。"""

from __future__ import annotations

from vibegoing.collab.routing import pick_pair, rank_souls
from vibegoing.soul import Soul


def _soul(name: str, capabilities: list[str]) -> Soul:
    return Soul(name=name, persona=f"{name} 伙伴", capabilities=capabilities)


def test_rank_by_capability_match():
    souls = [
        _soul("writer", ["写作"]),
        _soul("researcher", ["调研"]),
        _soul("engineer", ["工程"]),
    ]
    ranked = rank_souls("帮我调研多智能体框架并写摘要", souls)
    assert ranked[0].name == "researcher"
    assert ranked[1].name == "writer"


def test_rank_name_mention_beats_capability():
    souls = [_soul("ava", ["调研"]), _soul("bob", ["调研", "写作"])]
    ranked = rank_souls("让 ava 来调研这个课题", souls)
    assert ranked[0].name == "ava"


def test_rank_falls_back_to_original_order():
    souls = [_soul("first", ["法律"]), _soul("second", ["医疗"])]
    assert [s.name for s in rank_souls("和能力无关的任务", souls)] == ["first", "second"]


def test_pick_pair_returns_two_distinct():
    souls = [_soul("researcher", ["调研"]), _soul("writer", ["写作"]), _soul("engineer", ["工程"])]
    producer, reviewer = pick_pair("调研并写作", souls)
    assert producer.name == "researcher"
    assert reviewer.name == "writer"
    assert producer is not reviewer


def test_pick_pair_needs_two_souls():
    assert pick_pair("任务", [_soul("solo", ["调研"])]) is None


def test_capabilities_persisted_and_overridable(tmp_path):
    soul = Soul(name="bob", capabilities=["调研", "写作"])
    soul = soul.model_copy(update={"capabilities": ["法务"]})
    assert soul.capabilities == ["法务"]
