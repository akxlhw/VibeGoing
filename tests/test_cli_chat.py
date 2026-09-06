"""对话入口与 AI 人设解析的补充覆盖（VG-004）。"""

from __future__ import annotations

import vibegoing.cli as cli
import vibegoing.cli.chat as chat
import vibegoing.cli.soul_cmd as soul_cmd


class _FakeFlow:
    cli_runtime = None

    def __init__(self, soul, vibe_home, session_db=None):
        self.soul = soul

    def finalize_session_traces(self):
        pass

    def close(self):
        pass


def test_run_chat_banner_and_session_id(tmp_path, capsys, monkeypatch):
    recorded = {}
    monkeypatch.setattr(chat, "TeammateFlow", _FakeFlow)
    monkeypatch.setattr(chat, "run_repl", lambda flow, sid: recorded.update(sid=sid))

    cli.main(["--home", str(tmp_path)])

    out = capsys.readouterr().out
    assert "已就绪" in out
    assert f"会话 ID：{recorded['sid']}" in out
    assert recorded["sid"]  # 新会话生成了 uuid


def test_run_chat_resume_not_found_lists_sessions(tmp_path, capsys, monkeypatch):
    cli.main(["--home", str(tmp_path), "--resume", "no-such-id"])
    out = capsys.readouterr().out
    assert "找不到要恢复的会话" in out


def test_ai_persona_parses_json(monkeypatch):
    import vibegoing.llm_utils as llm_utils

    class StubLLM:
        def call(self, messages, **kwargs):
            return '{"persona": "严谨的法务顾问", "principles": ["引用条款"]}'

    monkeypatch.setattr(llm_utils, "default_llm", lambda model: StubLLM())
    persona, principles = soul_cmd._ai_persona("法务", "any/model")
    assert persona == "严谨的法务顾问"
    assert principles == ["引用条款"]


def test_ai_persona_fallback_to_raw_text(monkeypatch):
    import vibegoing.llm_utils as llm_utils

    class StubLLM:
        def call(self, messages, **kwargs):
            return "模型没按 JSON 输出的人设文本"

    monkeypatch.setattr(llm_utils, "default_llm", lambda model: StubLLM())
    persona, principles = soul_cmd._ai_persona("法务", "any/model")
    assert persona == "模型没按 JSON 输出的人设文本"
    assert principles == []
