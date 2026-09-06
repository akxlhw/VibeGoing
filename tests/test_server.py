"""M4 本地服务 API：伙伴/聊天/会话/任务/执行体/审批（替身 LLM，无 Key）。"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from vibegoing.server.app import create_app


class StubLLM:
    def __init__(self, reply=None):
        self.n = 0
        self.reply = reply

    def call(self, messages, **kwargs):
        self.n += 1
        return self.reply or f"回复{self.n}"


def _client(tmp_path: Path, llm_factory: Callable[[str], Any] | None = None) -> TestClient:
    # 测试默认关闭记忆（真实记忆链路需嵌入 Key，属 PO 演示项）
    app = create_app(tmp_path, llm_factory=llm_factory, memory_for=lambda soul: None)
    return TestClient(app)


def test_health_and_static_index(tmp_path):
    client = _client(tmp_path)
    health = client.get("/api/health").json()
    assert health["ok"] is True and health["version"]
    page = client.get("/")
    assert page.status_code == 200 and "VibeGoing" in page.text
    assert client.get("/style.css").status_code == 200
    assert client.get("/app.js").status_code == 200


def test_souls_crud(tmp_path):
    client = _client(tmp_path)
    # 默认开箱：自动出现 ava
    names = [s["name"] for s in client.get("/api/souls").json()]
    assert "ava" in names

    created = client.post(
        "/api/souls",
        json={
            "name": "bob",
            "emoji": "🔍",
            "persona": "复核员",
            "capabilities": ["复核"],
            "runtime": "llm",
        },
    )
    assert created.status_code == 200

    dup = client.post("/api/souls", json={"name": "bob"})
    assert dup.status_code == 409
    assert client.post("/api/souls", json={"bad": 1}).status_code == 422

    patched = client.patch("/api/souls/bob", json={"runtime": "codex"}).json()
    assert patched["runtime"] == "codex"
    assert client.get("/api/souls/nope").status_code == 404


def test_chat_roundtrip_and_session_continuity(tmp_path):
    stub = StubLLM()

    def factory(model):
        return stub

    client = _client(tmp_path, llm_factory=factory)
    r1 = client.post("/api/chat", json={"soul": "ava", "message": "第一句"}).json()
    r2 = client.post(
        "/api/chat", json={"soul": "ava", "message": "第二句", "session_id": r1["session_id"]}
    ).json()
    assert r1["session_id"] == r2["session_id"]  # 不传 session 也接续最近会话
    assert r2["reply"].startswith("回复2")  # 同一替身连续应答（会话状态恢复）

    history = client.get(f"/api/sessions/{r1['session_id']}/messages").json()
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]

    assert client.post("/api/chat", json={"soul": "ava", "message": "  "}).status_code == 422
    # 任意伙伴名均可开箱创建（与 CLI 语义一致）


def test_persona_draft_endpoint(tmp_path, monkeypatch):
    import vibegoing.llm_utils as llm_utils

    class Gen:
        def call(self, messages, **kwargs):
            return '{"persona": "严谨的法务顾问", "principles": ["引用条款"]}'

    monkeypatch.setattr(llm_utils, "default_llm", lambda model: Gen())
    client = _client(tmp_path)
    r = client.post("/api/persona-draft", json={"description": "法务顾问"}).json()
    assert r["persona"] == "严谨的法务顾问"
    assert client.post("/api/persona-draft", json={"description": ""}).status_code == 422


def test_runtimes_and_dangerous_labels(tmp_path):
    client = _client(tmp_path)
    runtimes = client.get("/api/runtimes").json()
    names = [r["name"] for r in runtimes]
    assert {"llm", "zcode", "kimi-code", "deepseek-harness"} <= set(names)

    labels = client.get("/api/dangerous-labels").json()
    assert "递归强制删除" in labels


def test_crew_run_lifecycle(tmp_path):
    def factory(model):
        return StubLLM()

    client = _client(tmp_path, llm_factory=factory)
    r = client.post("/api/crew/run", json={"task": "调研多智能体框架并写摘要"}).json()
    task_id = r["task_id"]

    for _ in range(50):  # 轮询至终态（stub LLM 秒级完成）
        got = client.get(f"/api/tasks/{task_id}").json()
        if got["task"]["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert got["task"]["status"] == "done"
    assert [s["stage"] for s in got["stages"]] == ["produce", "review", "finalize"]

    listing = client.get("/api/tasks").json()
    assert any(t["task_id"] == task_id for t in listing)
    assert client.get("/api/tasks/zzz").status_code == 404


def test_chat_with_cli_runtime_approval_flow(tmp_path):
    """CLI 伙伴：危险指令默认拒绝 → UI 放行标签后放行（VG-403 审批入口后端）。"""
    from vibegoing.runtimes.base import TaskHandle
    from vibegoing.runtimes.guard import PermissionDenied

    class GuardedRuntime:
        """走服务端构造的 guard（工厂经 registry 收到 guard 参数）→ 审批链路真实。"""

        name = "fake-cli"

        def __init__(self, guard=None):
            self.guard = guard

        def submit(self, task, *, on_event=None):
            decision = self.guard.check(task.instruction, task.workdir)
            if not decision.approved:
                raise PermissionDenied(decision)
            h = TaskHandle(self.name, "t1")
            h._complete("CLI 执行完成", None)
            return h

        def health(self):
            from vibegoing.runtimes.base import RuntimeHealth

            return RuntimeHealth(ok=True, detail="fake")

    from vibegoing.runtimes import registry

    registry.register_cli_runtime("fake-cli", lambda guard=None, **kw: GuardedRuntime(guard))
    try:
        client = _client(tmp_path)  # soul.runtime 走 fake-cli
        client.post("/api/souls", json={"name": "dev", "runtime": "fake-cli", "persona": ""})

        denied = client.post("/api/chat", json={"soul": "dev", "message": "sudo 安装依赖"}).json()
        assert denied["reply"].startswith("⚠️") and "危险操作" in denied["reply"]

        GuardedRuntime.approved_labels = ["提权执行"]
        approved = client.post(
            "/api/chat",
            json={
                "soul": "dev",
                "message": "sudo 安装依赖",
                "approved_dangerous": ["提权执行"],
            },
        ).json()
        assert approved["reply"] == "CLI 执行完成"
    finally:
        registry._CLI_FACTORIES.pop("fake-cli", None)


@pytest.mark.parametrize("path", ["/api/souls", "/api/runtimes"])
def test_endpoints_no_crash(tmp_path, path):
    assert _client(tmp_path).get(path).status_code == 200
