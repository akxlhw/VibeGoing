"""VG-101 会话持久化：跨实例/跨进程恢复对话。"""

from __future__ import annotations

from uuid import uuid4

from vibegoing.session import SessionStore
from vibegoing.soul import Soul
from vibegoing.teammate import TeammateFlow


class StubLLM:
    def call(self, messages, **kwargs):
        user_msgs = [m for m in messages if m.get("role") == "user"]
        return f"reply to: {user_msgs[-1]['content'] if user_msgs else '?'}"


def _soul():
    return Soul(name="ava", persona="测试伙伴", memory_enabled=False)


def test_session_restores_across_fresh_instances(tmp_path):
    """新进程（新 Flow 实例）同 session_id 继续对话，历史完整恢复。"""
    db = tmp_path / "sessions.db"
    session = str(uuid4())

    first = TeammateFlow(soul=_soul(), vibe_home=tmp_path, llm=StubLLM(), session_db=db)
    first.handle_turn("你好，我是大卫", session_id=session)
    first.handle_turn("我在写一个多智能体项目", session_id=session)

    # 模拟重启：全新实例、全新对象
    second = TeammateFlow(soul=_soul(), vibe_home=tmp_path, llm=StubLLM(), session_db=db)
    second.handle_turn("我刚说了什么名字？", session_id=session)

    user_msgs = [m.content for m in second.state.messages if m.role == "user"]
    assert user_msgs == ["你好，我是大卫", "我在写一个多智能体项目", "我刚说了什么名字？"]


def test_session_store_lists_and_previews(tmp_path):
    db = tmp_path / "sessions.db"
    session = str(uuid4())

    flow = TeammateFlow(soul=_soul(), vibe_home=tmp_path, llm=StubLLM(), session_db=db)
    flow.handle_turn("帮我调研多智能体框架", session_id=session)

    store = SessionStore(db)
    sessions = store.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].session_id == session
    assert sessions[0].message_count == 2  # 一问一答
    assert "帮我调研多智能体框架" in sessions[0].preview


def test_session_resolve_latest_exact_and_prefix(tmp_path):
    db = tmp_path / "sessions.db"
    flow = TeammateFlow(soul=_soul(), vibe_home=tmp_path, llm=StubLLM(), session_db=db)
    older, newer = str(uuid4()), str(uuid4())
    flow.handle_turn("第一段", session_id=older)
    flow.handle_turn("第二段", session_id=newer)

    store = SessionStore(db)
    assert store.resolve(None) == newer  # 不带参数 → 最近会话
    assert store.resolve(older) == older  # 精确匹配
    assert store.resolve("nonexistent") is None
