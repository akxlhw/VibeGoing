"""VG-303 Codex 适配器与"换绑不换脑"验证。"""

from __future__ import annotations

import time

import pytest

from vibegoing.runtimes.base import RuntimeEvent, TaskSpec
from vibegoing.runtimes.claude_code import ClaudeCodeRuntime
from vibegoing.runtimes.codex import CodexRuntime
from vibegoing.runtimes.guard import PermissionDenied, PermissionGuard
from vibegoing.runtimes.registry import get_runtime
from vibegoing.soul import Soul


class FakeProcess:
    def __init__(self, lines, returncode=0, line_delay=0.0):
        self._lines = lines
        self.returncode = returncode
        self._line_delay = line_delay
        self.terminated = False

    @property
    def stdout(self):
        for line in self._lines:
            if self._line_delay:
                time.sleep(self._line_delay)
            yield line + "\n"

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.terminated = True


def _guard(tmp_path):
    return PermissionGuard(allowed_dirs=[tmp_path])


def test_codex_command_contract_and_output(tmp_path):
    spawned: dict = {}

    def spawn(argv, cwd):
        spawned["argv"], spawned["cwd"] = argv, cwd
        return FakeProcess(["正在分析…", "已修复 bug"])

    runtime = CodexRuntime(spawn=spawn, guard=_guard(tmp_path))
    events: list[RuntimeEvent] = []
    handle = runtime.submit(
        TaskSpec(instruction="修复 bug", workdir=tmp_path), on_event=events.append
    )

    assert handle.wait(timeout=5) == "正在分析…\n已修复 bug"
    assert spawned["argv"] == ["codex", "exec", "修复 bug"]
    assert [e.kind for e in events][-1] == "done"


def test_codex_guard_applies(tmp_path):
    runtime = CodexRuntime(spawn=lambda a, c: FakeProcess([]), guard=_guard(tmp_path))
    with pytest.raises(PermissionDenied, match="危险操作"):
        runtime.submit(TaskSpec(instruction="sudo rm x", workdir=tmp_path))


def test_registry_resolves_codex(tmp_path):
    runtime = get_runtime(Soul(name="ava", runtime="codex"), guard=_guard(tmp_path))
    assert runtime.name == "codex"


def test_rebind_runtime_keeps_brain(tmp_path):
    """换绑不换脑：同一 Soul 在 claude-code ↔ codex 间切换，
    身份、记忆 scope、会话不变，只有执行体换。"""
    soul = Soul(name="ava", persona="资深工程师", capabilities=["工程"], runtime="claude-code")
    claude = get_runtime(soul, guard=_guard(tmp_path))
    rebound = soul.model_copy(update={"runtime": "codex"})
    codex = get_runtime(rebound, guard=_guard(tmp_path))

    assert isinstance(claude, ClaudeCodeRuntime)
    assert isinstance(codex, CodexRuntime)
    # Soul 本体未被换绑修改
    assert soul.runtime == "claude-code"
    # 身份与协作属性不变
    assert rebound.identity_prompt() == soul.identity_prompt()
    assert rebound.capabilities == soul.capabilities
    # 落盘的 Soul 数据不因运行时切换丢失字段
    assert rebound.model_dump()["persona"] == soul.model_dump()["persona"]


def test_unknown_runtime_rejected(tmp_path):
    try:
        get_runtime(Soul(name="x", runtime="ghost"), guard=_guard(tmp_path))
        raise AssertionError("应当报错")
    except ValueError as exc:
        assert "未知 runtime" in str(exc)
