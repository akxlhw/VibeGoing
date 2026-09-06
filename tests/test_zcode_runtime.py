"""VG-307 ZCode 适配器：命令契约、二进制覆盖、门控、注册。"""

from __future__ import annotations

import sys

import pytest

from vibegoing.runtimes.base import TaskSpec
from vibegoing.runtimes.guard import PermissionDenied, PermissionGuard
from vibegoing.runtimes.registry import get_runtime
from vibegoing.runtimes.zcode import ZCodeRuntime
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


def test_zcode_command_contract(tmp_path):
    spawned: dict = {}

    def spawn(argv, cwd):
        spawned["argv"], spawned["cwd"] = argv, cwd
        return FakeProcess(["分析完成", "已修复"])

    runtime = ZCodeRuntime(spawn=spawn, guard=_guard(tmp_path))
    handle = runtime.submit(TaskSpec(instruction="修复这个 bug", workdir=tmp_path))

    assert handle.wait(timeout=5) == "分析完成\n已修复"
    assert spawned["argv"] == ["zcode", "-p", "修复这个 bug"]
    assert spawned["cwd"] == tmp_path.resolve()


def test_zcode_binary_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBE_ZCODE_BIN", sys.executable)
    runtime = ZCodeRuntime(spawn=lambda a, c: FakeProcess(["ok"]), guard=_guard(tmp_path))

    assert runtime.effective_binary == sys.executable
    assert runtime.health().ok  # sys.executable 一定可找到
    handle = runtime.submit(TaskSpec(instruction="任务", workdir=tmp_path))
    assert handle.wait(timeout=5) == "ok"


def test_zcode_guard_applies(tmp_path):
    runtime = ZCodeRuntime(spawn=lambda a, c: FakeProcess([]), guard=_guard(tmp_path))
    with pytest.raises(PermissionDenied, match="危险操作"):
        runtime.submit(TaskSpec(instruction="rm -rf / 数据清理", workdir=tmp_path))


def test_zcode_registered(tmp_path):
    runtime = get_runtime(Soul(name="dev", runtime="zcode"), guard=_guard(tmp_path))
    assert runtime.name == "zcode"
