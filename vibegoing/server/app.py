"""本地 Web 服务（M4 桌面化）：REST API + 静态前端。

只监听 127.0.0.1（本地优先红线：工作内容不出本机）。
create_app 工厂注入 home/llm_factory/memory_for，测试无需 API Key。
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..ledger import TaskLedger
from ..runtimes.guard import DANGEROUS_PATTERNS, PermissionGuard
from ..session import SessionStore
from ..soul import Soul, SoulStore, default_soul
from ..teammate import TeammateFlow, _build_memory

WEB_DIR = Path(__file__).parent.parent / "web"

# 危险模式标签（供前端审批入口渲染；与 guard.DANGEROUS_PATTERNS 同源）
DANGEROUS_LABELS = [label for _, label in DANGEROUS_PATTERNS]


class ChatRequest(BaseModel):
    soul: str
    message: str
    session_id: str | None = None
    approved_dangerous: list[str] = []  # 用户在 UI 上放行的危险标签


class CrewRunRequest(BaseModel):
    task: str
    mode: str = "review"
    producer: str | None = None
    reviewer: str | None = None
    manager: str | None = None


def create_app(
    home: Path,
    llm_factory: Callable[[str], Any] | None = None,
    memory_for: Callable[[Soul], Any] | None = None,
) -> FastAPI:
    """构造 VibeGoing 本地服务。注入点仅用于测试。"""
    app = FastAPI(title="VibeGoing", version="local")
    app.state.home = home
    app.state.llm_factory = llm_factory
    app.state.memory_for = memory_for

    def store() -> SoulStore:
        return SoulStore(home / "souls")

    def ledger() -> TaskLedger:
        return TaskLedger(home / "ledger.db")

    def sessions() -> SessionStore:
        return SessionStore(home / "sessions.db")

    def _load_soul(name: str) -> Soul:
        try:
            return store().load(name)
        except FileNotFoundError as exc:
            raise HTTPException(404, f"伙伴 {name} 不存在") from exc

    def _teammate(soul: Soul, approved: list[str] | None = None) -> TeammateFlow:
        kwargs: dict[str, Any] = {}
        if llm_factory is not None:
            kwargs["llm"] = llm_factory(soul.model)
        if soul.runtime not in ("llm", "", None):
            # CLI 伙伴：审批回调 = UI 上用户放行的危险标签自动通过
            from ..runtimes.registry import get_runtime

            allowed = set(approved or [])
            guard = PermissionGuard(
                allowed_dirs=[home.resolve()],
                approval=(
                    (lambda prompt: any(label in prompt for label in allowed)) if allowed else None
                ),
            )
            kwargs["cli_runtime"] = get_runtime(soul, guard=guard)
        flow = TeammateFlow(soul=soul, vibe_home=home, **kwargs)
        flow.cli_workdir = home.resolve()  # UI 场景默认工作区=VIBE_HOME，与白名单一致
        if memory_for is not None:
            flow.memory_backend = memory_for(soul)
        return flow

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": _app_version()}

    @app.get("/api/souls")
    def list_souls() -> list[dict]:
        st = store()
        st.load_or_create("ava", template=default_soul())
        return [st.load(name).model_dump() for name in st.list_names()]

    @app.post("/api/souls")
    def create_soul(payload: dict) -> dict:
        try:
            soul = Soul.model_validate(payload)
        except Exception as exc:
            raise HTTPException(422, f"Soul 数据非法：{exc}") from exc
        st = store()
        if st.exists(soul.name):
            raise HTTPException(409, f"伙伴 {soul.name} 已存在")
        st.save(soul)
        return soul.model_dump()

    @app.patch("/api/souls/{name}")
    def edit_soul(name: str, payload: dict) -> dict:
        soul = _load_soul(name)
        updates = {k: v for k, v in payload.items() if k in Soul.model_fields}
        soul = soul.model_copy(update=updates)
        store().save(soul)
        return soul.model_dump()

    @app.get("/api/runtimes")
    def list_runtimes() -> list[dict]:
        from ..runtimes.registry import get_runtime, runtime_names

        out = []
        for name in runtime_names():
            runtime = get_runtime(Soul(name="probe", runtime=name))
            health = runtime.health()
            out.append({"name": name, "ok": health.ok, "detail": health.detail})
        return out

    @app.get("/api/dangerous-labels")
    def dangerous_labels() -> list[str]:
        return DANGEROUS_LABELS

    @app.post("/api/chat")
    def chat(req: ChatRequest) -> dict:
        if not req.message.strip():
            raise HTTPException(422, "消息不能为空")
        # 与 CLI 对齐：不存在的伙伴按默认模板开箱创建（如全新环境的 ava）
        soul = store().load_or_create(req.soul, template=default_soul())
        flow = _teammate(soul, approved=req.approved_dangerous)
        session_id = req.session_id or sessions().resolve(None) or _new_session_id()
        try:
            try:
                reply = flow.handle_turn(req.message, session_id=session_id)
            except Exception as exc:  # 缺 Key/模型异常等：明示原因，不打断界面
                raise HTTPException(502, f"执行失败：{exc}") from exc
        finally:
            with contextlib.suppress(Exception):
                flow.close()
        return {"session_id": session_id, "reply": reply}

    @app.get("/api/sessions")
    def list_sessions() -> list[dict]:
        return [s.__dict__ for s in sessions().list_sessions()]

    @app.get("/api/sessions/{session_id}/messages")
    def session_messages(session_id: str) -> list[dict]:
        return sessions().messages(session_id)

    @app.post("/api/persona-draft")
    def persona_draft(payload: dict) -> dict:
        """Soul 一键生成 ✨（向导第 3 步；经 llm_utils 工厂，测试可注入）。"""
        from ..cli.soul_cmd import _ai_persona

        description = str(payload.get("description", "")).strip()
        if not description:
            raise HTTPException(422, "描述不能为空")
        model = str(payload.get("model") or "openai/gpt-4o")
        try:
            persona, principles = _ai_persona(description, model)
        except Exception as exc:
            raise HTTPException(502, f"生成失败：{exc}") from exc
        return {"persona": persona, "principles": principles}

    @app.get("/api/tasks")
    def list_tasks() -> list[dict]:
        return [t.__dict__ for t in ledger().list_tasks()]

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: str) -> dict:
        got = ledger().get(task_id)
        if got is None:
            raise HTTPException(404, f"任务 {task_id} 不存在")
        task, stages = got
        return {"task": task.__dict__, "stages": [s.__dict__ for s in stages]}

    @app.post("/api/crew/run")
    def crew_run(req: CrewRunRequest) -> dict:
        """协作任务：后台线程执行，前端轮询台账。"""
        from ..collab.pipeline import run_hierarchy_pipeline, run_review_pipeline
        from ..collab.routing import pick_pair
        from ..soul import default_reviewer_soul

        st = store()
        st.load_or_create("ava", template=default_soul())
        souls = [st.load(n) for n in st.list_names()]
        lg = ledger()
        record = lg.create_task(req.task, mode=req.mode)
        lg.set_status(record.task_id, "running")

        class _ReuseLedger:
            """让管线复用端点预建的台账记录（避免双记录）。"""

            def __init__(self, inner: TaskLedger, reuse):
                self._inner, self._reuse = inner, reuse

            def create_task(self, description: str, mode: str):
                return self._reuse

            def __getattr__(self, name: str):
                return getattr(self._inner, name)

        pipeline_ledger = cast(TaskLedger, _ReuseLedger(lg, record))

        def worker() -> None:
            try:
                mem_for = app.state.memory_for or (lambda soul: _build_memory(soul, home))
                if req.mode == "hierarchy":
                    manager = st.load(req.manager or souls[0].name)
                    run_hierarchy_pipeline(
                        req.task,
                        manager,
                        souls,
                        home,
                        llm_factory=llm_factory,
                        ledger=pipeline_ledger,
                        memory_for=mem_for,
                    )
                else:
                    producer = st.load(req.producer) if req.producer else None
                    reviewer = st.load(req.reviewer) if req.reviewer else None
                    if producer is None or reviewer is None:
                        routed = pick_pair(req.task, souls)
                        if routed is not None:
                            producer = producer or routed[0]
                            if reviewer is None and routed[1].name != producer.name:
                                reviewer = routed[1]
                    if producer is None:
                        producer = souls[0]
                    if reviewer is None or reviewer.name == producer.name:
                        reviewer = st.load_or_create("bob", template=default_reviewer_soul())
                    run_review_pipeline(
                        req.task,
                        producer,
                        reviewer,
                        home,
                        llm_factory=llm_factory,
                        ledger=pipeline_ledger,
                        memory_for=mem_for,
                    )
            except Exception as exc:
                lg.add_stage(record.task_id, "error", "server", f"失败：{exc}")
                lg.set_status(record.task_id, "failed")

        threading.Thread(target=worker, daemon=True).start()
        return {"task_id": record.task_id}

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def _new_session_id() -> str:
    from uuid import uuid4

    return str(uuid4())


def _app_version() -> str:
    from .. import __version__

    return __version__
