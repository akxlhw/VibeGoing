"""v0.1.0 发布补充测试：覆盖发布验收所需的行为面。"""

from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path

import tomllib

from vibegoing import __version__
from vibegoing.__main__ import main
from vibegoing.soul import Soul, SoulStore, default_soul
from vibegoing.teammate import TeammateFlow


class StubLLM:
    def call(self, messages, **kwargs):
        return "stub reply"


def test_identity_prompt_renders_sections():
    soul = Soul(name="ava", persona="资深工程师", principles=["先给结论"])
    prompt = soul.identity_prompt()
    assert "资深工程师" in prompt
    assert "先给结论" in prompt
    assert "# 你是谁" in prompt and "# 工作原则" in prompt


def test_identity_prompt_empty_soul():
    assert Soul(name="empty").identity_prompt() == ""


def test_teammate_without_memory(tmp_path):
    soul = Soul(name="ava", memory_enabled=False)
    flow = TeammateFlow(soul=soul, vibe_home=tmp_path, llm=StubLLM())
    assert flow.memory_backend is None
    # 无记忆路径下对话与关闭均正常
    flow.handle_turn("你好", session_id="s1")
    assert flow.state.messages[-1].role == "assistant"
    flow.close()  # 不应抛异常


def test_cli_list_souls(tmp_path, capsys, monkeypatch):
    store = SoulStore(tmp_path / "souls")
    store.save(default_soul())
    monkeypatch.setattr(sys, "argv", ["vibegoing", "--home", str(tmp_path), "--list"])
    main()
    assert "ava" in capsys.readouterr().out


def test_version_consistency():
    """发布纪律守卫：pyproject / __version__ / 安装元数据三处版本一致。"""
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    with pyproject.open("rb") as f:
        declared = tomllib.load(f)["project"]["version"]
    assert declared == __version__ == importlib.metadata.version("vibegoing")
