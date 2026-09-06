"""VG-105 模型热切换：--model 覆盖 Soul 绑定，身份与记忆不变。"""

from __future__ import annotations

import argparse

from vibegoing.cli.chat import prepare_soul as prepare
from vibegoing.soul import Soul, SoulStore


def _args(model=None, soul_name="ava"):
    return argparse.Namespace(model=model, soul=soul_name)


def _store(tmp_path):
    store = SoulStore(tmp_path / "souls")
    store.save(Soul(name="ava", persona="测试", model="openai/gpt-4o"))
    return store


def test_model_flag_overrides_soul(tmp_path):
    store = _store(tmp_path)
    soul = prepare(_args(model="kimi/k2"), store)
    assert soul.model == "kimi/k2"
    # 覆盖只影响本次会话对象，落盘的 Soul 不变
    assert store.load("ava").model == "openai/gpt-4o"


def test_model_flag_wins_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBE_LLM", "deepseek/deepseek-chat")
    store = _store(tmp_path)
    assert prepare(_args(model="kimi/k2"), store).model == "kimi/k2"


def test_env_fallback_when_no_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBE_LLM", "deepseek/deepseek-chat")
    store = _store(tmp_path)
    assert prepare(_args(), store).model == "deepseek/deepseek-chat"


def test_identity_and_memory_scope_unchanged_after_override(tmp_path):
    """换引擎不换大脑：覆盖模型后身份 prompt 与记忆 scope 保持不变。"""
    store = _store(tmp_path)
    original = prepare(_args(), store)
    swapped = prepare(_args(model="anthropic/claude-sonnet-4"), store)
    assert swapped.identity_prompt() == original.identity_prompt()
    assert swapped.name == original.name
