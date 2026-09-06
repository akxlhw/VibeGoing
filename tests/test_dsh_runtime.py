"""VG-309 DeepSeek Harness 适配器。"""

from __future__ import annotations

import pytest

from vibegoing.runtimes.base import TaskSpec
from vibegoing.runtimes.deepseek import DeepSeekHarnessRuntime
from vibegoing.runtimes.guard import PermissionGuard
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


def test_dsh_command_contract(tmp_path):
    """契约（官方 README）：dsh --profile headless <job>，打印最终答案后退出。"""
    spawned: dict = {}

    def spawn(argv, cwd):
        spawned["argv"], spawned["cwd"] = argv, cwd
        return FakeProcess(["会话启动", "最终答案：测试全绿"])

    runtime = DeepSeekHarnessRuntime(spawn=spawn, guard=_guard(tmp_path))
    handle = runtime.submit(TaskSpec(instruction="跑通测试", workdir=tmp_path))

    assert handle.wait(timeout=5).endswith("最终答案：测试全绿")
    assert spawned["argv"] == ["dsh", "--profile", "headless", "跑通测试"]
    assert spawned["cwd"] == tmp_path.resolve()  # dsh 以调用目录为工作区根


def test_dsh_nonzero_exit(tmp_path):
    runtime = DeepSeekHarnessRuntime(
        spawn=lambda a, c: FakeProcess(["部分输出"], returncode=1), guard=_guard(tmp_path)
    )
    handle = runtime.submit(TaskSpec(instruction="任务", workdir=tmp_path))
    with pytest.raises(RuntimeError, match="退出码 1"):
        handle.wait(timeout=5)


def test_dsh_registered_and_listed(tmp_path):
    runtime = get_runtime(Soul(name="dev", runtime="deepseek-harness"), guard=_guard(tmp_path))
    assert runtime.name == "deepseek-harness"
    assert "deepseek-harness" in runtime_names()
