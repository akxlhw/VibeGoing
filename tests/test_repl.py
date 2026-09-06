"""VG-104 流式输出：stream_turn 接入 REPL。"""

from __future__ import annotations

from vibegoing.cli import _run_repl
from vibegoing.soul import Soul
from vibegoing.teammate import TeammateFlow


class StubLLM:
    """不支持流式的替身：走整段回退路径。"""

    def call(self, messages, **kwargs):
        user_msgs = [m for m in messages if m.get("role") == "user"]
        return f"reply to: {user_msgs[-1]['content'] if user_msgs else '?'}"


def _flow(tmp_path, db=None):
    soul = Soul(name="ava", persona="测试", memory_enabled=False)
    return TeammateFlow(soul=soul, vibe_home=tmp_path, llm=StubLLM(), session_db=db)


def test_stream_turn_roundtrip(tmp_path):
    flow = _flow(tmp_path)
    stream = flow.stream_turn("你好", session_id="s-stream")
    with stream:
        consumed = list(stream.events)  # 必须在 with 内消费事件流
    assert consumed  # 事件流有帧（flow/lifecycle 等）
    assert "reply to: 你好" in str(stream.result)
    assert flow.state.messages[-1].role == "assistant"


def test_repl_fallback_prints_result(tmp_path, capsys):
    flow = _flow(tmp_path, db=tmp_path / "s.db")
    inputs = iter(["第一句", "exit"])

    _run_repl(flow, "s-repl", input_fn=lambda prompt: next(inputs))

    out = capsys.readouterr().out
    assert "Assistant: reply to: 第一句" in out


def test_repl_persists_for_resume(tmp_path):
    db = tmp_path / "s.db"
    first = _flow(tmp_path, db=db)
    inputs = iter(["记住了", "exit"])
    _run_repl(first, "s-keep", input_fn=lambda prompt: next(inputs))

    second = TeammateFlow(
        soul=Soul(name="ava", memory_enabled=False),
        vibe_home=tmp_path,
        llm=StubLLM(),
        session_db=db,
    )
    second.handle_turn("然后呢", session_id="s-keep")
    user_msgs = [m.content for m in second.state.messages if m.role == "user"]
    assert user_msgs == ["记住了", "然后呢"]


def test_repl_exit_and_empty_inputs(tmp_path, capsys):
    flow = _flow(tmp_path)
    inputs = iter(["", "   ", "exit"])

    _run_repl(flow, "s-x", input_fn=lambda prompt: next(inputs))

    out = capsys.readouterr().out
    assert "Assistant:" not in out  # 空输入不触发回合
