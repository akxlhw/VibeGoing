"""冒烟测试：不依赖任何 API Key，验证会话循环与 Soul 存取。"""

from __future__ import annotations

from uuid import uuid4

from vibegoing.soul import Soul, SoulStore, default_soul
from vibegoing.teammate import TeammateFlow


class StubLLM:
    """替身 LLM：回显最后一条用户消息。"""

    def call(self, messages, **kwargs):
        user_msgs = [m for m in messages if m.get("role") == "user"]
        return f"stub reply to: {user_msgs[-1]['content'] if user_msgs else '?'}"


def _teammate(tmp_path, memory_enabled=False):
    soul = Soul(
        name="ava",
        persona="测试伙伴",
        principles=["先给结论"],
        memory_enabled=memory_enabled,
    )
    return TeammateFlow(soul=soul, vibe_home=tmp_path, llm=StubLLM())


def test_conversation_turn_roundtrip(tmp_path):
    flow = _teammate(tmp_path)
    session = str(uuid4())

    result = flow.handle_turn("你好", session_id=session)
    assert "stub reply to: 你好" in str(result)

    # 用户消息与助手回复都进入会话历史
    roles = [m.role for m in flow.state.messages]
    assert roles[-2:] == ["user", "assistant"]

    # 同一 session 多轮对话
    flow.handle_turn("第二句", session_id=session)
    user_contents = [m.content for m in flow.state.messages if m.role == "user"]
    assert user_contents == ["你好", "第二句"]


def test_system_prompt_injects_soul_identity(tmp_path):
    flow = _teammate(tmp_path)
    prompt = flow._system_prompt([])
    assert "测试伙伴" in prompt
    assert "先给结论" in prompt


def test_soul_store_roundtrip(tmp_path):
    store = SoulStore(tmp_path / "souls")
    soul = default_soul()

    store.save(soul)
    assert store.list_names() == ["ava"]

    loaded = store.load("ava")
    assert loaded.persona == soul.persona
    assert loaded.model == soul.model

    created = store.load_or_create("bob")
    assert created.name == "bob"
    assert created.persona == soul.persona  # 模板身份，名字换成新伙伴


def test_memory_scope_naming(tmp_path):
    flow = _teammate(tmp_path)
    assert flow._memory_scope == "teammates/ava"
