"""VG-308 Kimi Code 适配器。"""

from __future__ import annotations

import pytest

from vibegoing.runtimes.base import TaskSpec
from vibegoing.runtimes.guard import PermissionDenied, PermissionGuard
from vibegoing.runtimes.kimi_code import KimiCodeRuntime
from vibegoing.runtimes.registry import get_runtime, runtime_names
from vibegoing.soul import Soul


class FakeProcess:
    def __init__(self, lines, returncode=0):
        self._lines = lines
        self.returncode = returncode

    @property
    def stdout(self):
        yield from (line + "\n" for line in self._lines)

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        pass


def _guard(tmp_path):
    return PermissionGuard(allowed_dirs=[tmp_path])


def test_kimi_command_contract(tmp_path):
    """契约（真机实测修正）：-p 无头；--auto 与 -p 互斥，不可携带。"""
    spawned: dict = {}

    def spawn(argv, cwd):
        spawned["argv"], spawned["cwd"] = argv, cwd
        return FakeProcess(["分析中", "修复完成"])

    runtime = KimiCodeRuntime(spawn=spawn, guard=_guard(tmp_path))
    handle = runtime.submit(TaskSpec(instruction="修个 bug", workdir=tmp_path))

    assert handle.wait(timeout=5) == "分析中\n修复完成"
    assert spawned["argv"] == ["kimi", "-p", "修个 bug"]
    assert spawned["cwd"] == tmp_path.resolve()


def test_kimi_guard_applies(tmp_path):
    runtime = KimiCodeRuntime(spawn=lambda a, c: FakeProcess([]), guard=_guard(tmp_path))
    with pytest.raises(PermissionDenied):
        runtime.submit(TaskSpec(instruction="sudo 搞定它", workdir=tmp_path))


def test_kimi_registered_and_listed(tmp_path):
    runtime = get_runtime(Soul(name="dev", runtime="kimi-code"), guard=_guard(tmp_path))
    assert runtime.name == "kimi-code"
    assert "kimi-code" in runtime_names()


def test_kimi_health_hint(tmp_path, monkeypatch):
    monkeypatch.delenv("VIBE_KIMI_CODE_BIN", raising=False)
    health = KimiCodeRuntime(guard=_guard(tmp_path)).health()
    if not health.ok:  # 未装 kimi 时提示二进制覆盖方式
        assert "VIBE_KIMI_CODE_BIN" in health.detail
