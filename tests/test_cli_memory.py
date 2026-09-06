"""VG-103 记忆管理命令：list/show/forget。

用注入的假后端测 CLI 行为（真实后端的写入/召回依赖 embedding，
属验收演示项，见 docs/agile/releases/v0.2.0.md）。
"""

from __future__ import annotations

from crewai.memory.types import MemoryRecord

import vibegoing.cli as cli
import vibegoing.cli.memory_cmd as memory_cmd


class FakeMemory:
    def __init__(self, records):
        self.records = records
        self.captured_scope = None
        self.forgotten: list[str] = []

    def list_records(self, scope=None, limit=200, offset=0):
        self.captured_scope = scope
        return self.records[:limit]

    def forget(self, record_ids=None, **kwargs):
        self.forgotten = record_ids or []
        self.records = [r for r in self.records if r.id not in self.forgotten]
        return len(self.forgotten)


def _record(rid: str, content: str, scope: str = "/") -> MemoryRecord:
    return MemoryRecord(id=rid, content=content, scope=scope, categories=["conversation"])


def _install(monkeypatch, fake):
    monkeypatch.setattr(memory_cmd, "build_admin_memory", lambda home: fake)


def test_memory_list_and_soul_filter(tmp_path, capsys, monkeypatch):
    fake = FakeMemory(
        [
            _record("aaa111", "用户喜欢简洁的回答"),
            _record("bbb222", "项目名是 VibeGoing"),
        ]
    )
    _install(monkeypatch, fake)

    cli.main(["--home", str(tmp_path), "memory", "list", "--soul", "bob"])
    out = capsys.readouterr().out
    assert "aaa111" in out and "用户喜欢简洁的回答" in out
    assert fake.captured_scope == "teammates/bob"

    cli.main(["--home", str(tmp_path), "memory", "list"])
    assert fake.captured_scope is None  # 不带 --soul 看全部


def test_memory_show_by_prefix(tmp_path, capsys, monkeypatch):
    fake = FakeMemory([_record("aaa111", "完整内容：用户在做多智能体产品")])
    _install(monkeypatch, fake)

    cli.main(["--home", str(tmp_path), "memory", "show", "aaa"])
    out = capsys.readouterr().out
    assert "aaa111" in out and "完整内容" in out

    cli.main(["--home", str(tmp_path), "memory", "show", "zzz"])
    assert "找不到记忆" in capsys.readouterr().out


def test_memory_forget_by_ids(tmp_path, capsys, monkeypatch):
    fake = FakeMemory([_record("aaa111", "记录一"), _record("bbb222", "记录二")])
    _install(monkeypatch, fake)

    cli.main(["--home", str(tmp_path), "memory", "forget", "aaa111", "bbb222"])
    out = capsys.readouterr().out
    assert "已遗忘 2 条记忆" in out
    assert fake.records == []
