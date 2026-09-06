"""VG-102 Soul 管理命令：create/edit/show/list 与 --ai 生成。"""

from __future__ import annotations

import vibegoing.cli as cli
import vibegoing.cli.soul_cmd as soul_cmd
from vibegoing.soul import SoulStore


def _run(tmp_path, *argv):
    cli.main(["--home", str(tmp_path), *argv])


def test_soul_create_show_list(tmp_path, capsys):
    _run(
        tmp_path,
        "soul",
        "create",
        "bob",
        "--emoji",
        "🧪",
        "--persona",
        "测试工程师伙伴",
        "--principles",
        "先给结论, 不猜需求",
        "--model",
        "deepseek/deepseek-chat",
    )
    out = capsys.readouterr().out
    assert "已创建 🧪 bob" in out

    _run(tmp_path, "soul", "show", "bob")
    out = capsys.readouterr().out
    assert "测试工程师伙伴" in out
    assert "deepseek/deepseek-chat" in out
    assert "先给结论" in out

    _run(tmp_path, "soul", "list")
    assert "bob" in capsys.readouterr().out


def test_soul_create_duplicate_rejected(tmp_path, capsys):
    _run(tmp_path, "soul", "create", "bob", "--persona", "第一版")
    _run(tmp_path, "soul", "create", "bob", "--persona", "第二版")
    assert "已存在" in capsys.readouterr().out
    assert SoulStore(tmp_path / "souls").load("bob").persona == "第一版"


def test_soul_create_with_ai(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        soul_cmd, "_ai_persona", lambda desc, model: ("AI 生成的人设", ["原则一", "原则二"])
    )
    _run(tmp_path, "soul", "create", "cici", "--ai", "一位严谨的法务顾问")
    out = capsys.readouterr().out
    assert "已创建" in out
    soul = SoulStore(tmp_path / "souls").load("cici")
    assert soul.persona == "AI 生成的人设"
    assert soul.principles == ["原则一", "原则二"]


def test_soul_create_ai_failure_is_actionable(tmp_path, capsys, monkeypatch):
    def boom(desc, model):
        raise RuntimeError("401 unauthorized")

    monkeypatch.setattr(soul_cmd, "_ai_persona", boom)
    _run(tmp_path, "soul", "create", "dodo", "--ai", "测试")
    out = capsys.readouterr().out
    assert "AI 生成人设失败" in out and "API Key" in out
    assert not SoulStore(tmp_path / "souls").exists("dodo")


def test_soul_edit_partial_update(tmp_path, capsys):
    _run(
        tmp_path,
        "soul",
        "create",
        "bob",
        "--persona",
        "原人设",
        "--model",
        "openai/gpt-4o",
        "--principles",
        "原原则",
    )
    _run(tmp_path, "soul", "edit", "bob", "--model", "kimi/k2", "--no-memory")
    out = capsys.readouterr().out
    assert "已更新 bob" in out

    soul = SoulStore(tmp_path / "souls").load("bob")
    assert soul.model == "kimi/k2"  # 已改
    assert soul.memory_enabled is False  # 已改
    assert soul.persona == "原人设"  # 未动
    assert soul.principles == ["原原则"]  # 未动
