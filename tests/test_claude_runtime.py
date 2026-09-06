"""VG-302 Claude Code 适配器：命令契约、stream-json 解析、门控/超时/取消。"""

from __future__ import annotations

import sys
import time

import pytest

from vibegoing.runtimes.base import RuntimeEvent, TaskSpec
from vibegoing.runtimes.claude_code import ClaudeCodeRuntime
from vibegoing.runtimes.cli_base import real_spawn
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


def _guard(tmp_path, **kw):
    return PermissionGuard(allowed_dirs=[tmp_path], **kw)


def _claude_stream():
    return [
        '{"type":"system","subtype":"init"}',
        '{"type":"assistant","message":{"content":[{"type":"text","text":"分析中…"}]}}',
        '{"type":"assistant","message":{"content":[{"type":"text","text":"继续"}]}}',
        '{"type":"result","subtype":"success","result":"修复完成：改为空值守护"}',
    ]


def test_command_contract_and_streaming(tmp_path):
    spawned: dict = {}

    def spawn(argv, cwd):
        spawned["argv"], spawned["cwd"] = argv, cwd
        return FakeProcess(_claude_stream())

    runtime = ClaudeCodeRuntime(spawn=spawn, guard=_guard(tmp_path))
    events: list[RuntimeEvent] = []
    handle = runtime.submit(
        TaskSpec(instruction="修复这个 bug", workdir=tmp_path), on_event=events.append
    )

    assert handle.wait(timeout=5) == "修复完成：改为空值守护"
    assert spawned["argv"] == [
        "claude",
        "-p",
        "修复这个 bug",
        "--output-format",
        "stream-json",
    ]
    assert spawned["cwd"] == tmp_path.resolve()
    stdout_events = [e.content for e in events if e.kind == "stdout"]
    assert "分析中…" in stdout_events and "继续" in stdout_events


def test_denied_by_guard_never_spawns(tmp_path):
    spawn_calls = []

    runtime = ClaudeCodeRuntime(
        spawn=lambda argv, cwd: spawn_calls.append(argv) or FakeProcess([]),
        guard=_guard(tmp_path),
    )
    with pytest.raises(PermissionDenied):
        runtime.submit(TaskSpec(instruction="rm -rf /", workdir=tmp_path))
    assert spawn_calls == []  # 红线：拒绝即不启动进程


def test_workdir_outside_whitelist_denied(tmp_path):
    runtime = ClaudeCodeRuntime(spawn=lambda a, c: FakeProcess([]), guard=_guard(tmp_path))
    with pytest.raises(PermissionDenied, match="白名单"):
        runtime.submit(TaskSpec(instruction="正常指令", workdir=tmp_path.parent))


def test_timeout_terminates_process(tmp_path):
    slow = FakeProcess(["line"] * 20, line_delay=0.05)
    runtime = ClaudeCodeRuntime(spawn=lambda a, c: slow, guard=_guard(tmp_path))
    handle = runtime.submit(TaskSpec(instruction="任务", workdir=tmp_path, timeout_s=0.08))

    with pytest.raises(RuntimeError, match="超"):
        handle.wait(timeout=10)
    assert slow.terminated


def test_cancel_terminates(tmp_path):
    slow = FakeProcess(["line"] * 100, line_delay=0.05)
    runtime = ClaudeCodeRuntime(spawn=lambda a, c: slow, guard=_guard(tmp_path))
    handle = runtime.submit(TaskSpec(instruction="任务", workdir=tmp_path))
    time.sleep(0.12)
    runtime.cancel(handle)

    with pytest.raises(RuntimeError, match="已取消"):
        handle.wait(timeout=10)
    assert slow.terminated


def test_nonzero_exit_is_error_with_output_tail(tmp_path):
    runtime = ClaudeCodeRuntime(
        spawn=lambda a, c: FakeProcess(_claude_stream(), returncode=2),
        guard=_guard(tmp_path),
    )
    handle = runtime.submit(TaskSpec(instruction="任务", workdir=tmp_path))
    with pytest.raises(RuntimeError, match="退出码 2"):
        handle.wait(timeout=10)

    # 退出码错误需携带输出尾部（可诊断性：stderr 合并进 stdout）
    runtime2 = ClaudeCodeRuntime(
        spawn=lambda a, c: FakeProcess(["error: Cannot combine flags"], returncode=1),
        guard=_guard(tmp_path),
    )
    handle2 = runtime2.submit(TaskSpec(instruction="任务", workdir=tmp_path))
    with pytest.raises(RuntimeError, match="Cannot combine flags"):
        handle2.wait(timeout=10)


def test_parse_line_variants():
    runtime = ClaudeCodeRuntime()
    assert runtime.parse_line("") == []
    # 非 JSON 行透传
    assert runtime.parse_line("raw output") == [RuntimeEvent(kind="stdout", content="raw output")]
    # result 行产出 done 事件
    events = runtime.parse_line('{"type":"result","result":"最终"}')
    assert events == [RuntimeEvent(kind="done", content="最终")]


def test_registry_resolves_claude_code(tmp_path):
    soul = Soul(name="ava", runtime="claude-code")
    runtime = get_runtime(soul, guard=_guard(tmp_path))
    assert runtime.name == "claude-code"


def test_real_spawn_runs_harmless_process(tmp_path):
    """真实 subprocess 路径：用无害 python 命令覆盖 real_spawn 代码路径。"""

    class PythonRuntime(ClaudeCodeRuntime):
        name, binary = "py-test", sys.executable

        def build_command(self, task):
            return [sys.executable, "-c", "print('real-ok')"]

    runtime = PythonRuntime(guard=_guard(tmp_path))
    handle = runtime.submit(TaskSpec(instruction="x", workdir=tmp_path))
    assert "real-ok" in handle.wait(timeout=15)


def test_real_spawn_happy_path(tmp_path):
    proc = real_spawn([sys.executable, "-c", "print('ok')"], tmp_path)
    assert proc.wait(timeout=15) == 0
