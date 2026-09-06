"""M3 集成：伙伴绑定 CLI Runtime——会话路径、台账、CLI 命令。"""

from __future__ import annotations

import threading
import uuid

import vibegoing.cli as cli
from vibegoing.ledger import TaskLedger
from vibegoing.runtimes.base import (
    Runtime,
    RuntimeEvent,
    RuntimeHealth,
    TaskHandle,
    TaskSpec,
)
from vibegoing.runtimes.guard import GuardDecision, PermissionDenied
from vibegoing.soul import Soul, SoulStore
from vibegoing.teammate import TeammateFlow


class OkRuntime(Runtime):
    name = "fake-cli"

    def __init__(self, output="CLI 执行产出：修复完成"):
        self.output = output
        self.specs: list[TaskSpec] = []

    def submit(self, task, *, on_event=None):
        self.specs.append(task)
        handle = TaskHandle(self.name, uuid.uuid4().hex[:8])

        def finish():
            if on_event:
                on_event(RuntimeEvent(kind="stdout", content=self.output))
            handle._complete(self.output, None)

        threading.Timer(0.01, finish).start()
        return handle

    def health(self):
        return RuntimeHealth(ok=True, detail="fake")


class DeniedRuntime(Runtime):
    name = "fake-denied"

    def submit(self, task, *, on_event=None):
        raise PermissionDenied(GuardDecision(approved=False, reason="不在白名单内"))

    def health(self):
        return RuntimeHealth(ok=False, detail="fake")


def _flow(tmp_path, runtime, name="ava"):
    soul = Soul(name=name, persona="工程师", memory_enabled=False, runtime="claude-code")
    return TeammateFlow(soul=soul, vibe_home=tmp_path, llm=None, cli_runtime=runtime)


def test_cli_runtime_turn_roundtrip(tmp_path):
    runtime = OkRuntime()
    flow = _flow(tmp_path, runtime)

    result = flow.handle_turn("修复这个 bug", session_id="s-cli")

    assert result == "CLI 执行产出：修复完成"
    assert flow.state.messages[-1].role == "assistant"
    # 指令包含身份与用户指令
    instruction = runtime.specs[0].instruction
    assert "工程师" in instruction and "修复这个 bug" in instruction
    # 台账记录了 CLI 任务
    ledger = TaskLedger(tmp_path / "ledger.db")
    record = ledger.list_tasks()[0]
    assert record.status == "done" and record.mode == "cli:fake-cli"


def test_cli_runtime_denied_keeps_session(tmp_path):
    flow = _flow(tmp_path, DeniedRuntime())
    result = flow.handle_turn("随便干点啥", session_id="s-deny")

    assert "⚠️ CLI 执行失败" in result and "白名单" in result
    ledger = TaskLedger(tmp_path / "ledger.db")
    assert ledger.list_tasks()[0].status == "failed"
    # 会话仍在，可以继续下一轮
    assert len(flow.state.messages) == 2


def test_runtime_event_forwarded(tmp_path):
    seen: list[RuntimeEvent] = []
    runtime = OkRuntime()
    flow = _flow(tmp_path, runtime)
    flow.on_runtime_event = seen.append
    flow.handle_turn("任务", session_id="s-evt")
    assert any(e.kind == "stdout" and "修复完成" in e.content for e in seen)


def test_soul_runtime_flag_end_to_end(tmp_path, capsys):
    cli.main(
        [
            "--home",
            str(tmp_path),
            "soul",
            "create",
            "dev",
            "--persona",
            "编码伙伴",
            "--runtime",
            "claude-code",
        ]
    )
    out = capsys.readouterr().out
    assert "执行体：claude-code" in out
    assert SoulStore(tmp_path / "souls").load("dev").runtime == "claude-code"

    cli.main(["--home", str(tmp_path), "soul", "edit", "dev", "--runtime", "codex"])
    assert "已更新" in capsys.readouterr().out
    assert SoulStore(tmp_path / "souls").load("dev").runtime == "codex"


def test_runtime_list_command(tmp_path, capsys):
    cli.main(["--home", str(tmp_path), "runtime", "list"])
    out = capsys.readouterr().out
    assert "llm" in out and "claude-code" in out and "codex" in out

    cli.main(["--home", str(tmp_path), "runtime", "check", "llm"])
    out = capsys.readouterr().out
    assert "✅ llm" in out


def test_chat_banner_shows_runtime(tmp_path, capsys, monkeypatch):
    recorded = {}
    SoulStore(tmp_path / "souls").save(Soul(name="dev", persona="编码伙伴", runtime="claude-code"))

    class FakeFlow:
        cli_runtime = object()  # 绑定了 CLI 执行体

        def __init__(self, soul, vibe_home, session_db=None):
            recorded["soul"] = soul

        def finalize_session_traces(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(cli, "TeammateFlow", FakeFlow)
    monkeypatch.setattr(cli, "_run_repl", lambda flow, sid: recorded.update(sid=sid))
    cli.main(["--home", str(tmp_path), "--soul", "dev"])

    out = capsys.readouterr().out
    assert "执行体：claude-code" in out
