"""会话型伙伴：把 Soul 人设与长期记忆注入每一轮对话。

基于 CrewAI 的 conversational Flow：每条用户消息是一轮 handle_turn，
伙伴的回复经由统一 Memory 做长期记忆的召回与沉淀。
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

from crewai.flow import ConversationConfig, ConversationState, Flow
from crewai.flow.persistence import SQLiteFlowPersistence, persist
from crewai.llms.base_llm import BaseLLM
from crewai.memory.unified_memory import Memory
from crewai.utilities.types import LLMMessage

from .soul import Soul


@persist()
@ConversationConfig(defer_trace_finalization=True)
class TeammateFlow(Flow[ConversationState]):
    """一位常驻伙伴：turn 开始前召回记忆，turn 结束后沉淀记忆。

    会话快照持久化到 vibe_home/sessions.db（可用 session_db 覆盖路径）：
    类级 ``@persist()`` 启用快照机制，实例后端在 __init__ 中指向本地库。
    """

    def __init__(
        self,
        soul: Soul,
        vibe_home: Path,
        llm: Any | None = None,
        memory: Memory | None = None,
        session_db: Path | None = None,
        recall_min_score: float | None = None,
        cli_runtime: Any | None = None,
    ):
        super().__init__()
        self.soul = soul
        self.vibe_home = vibe_home
        self._llm = llm if llm is not None else _default_llm(soul.model)
        # 命名为 memory_backend 而非 memory：RuntimeFlow 基类已声明 memory 字段
        # （Memory | MemoryScope | MemorySlice），避免与框架字段冲突
        self.memory_backend = memory if memory is not None else _build_memory(soul, vibe_home)
        # 会话持久化：实例后端覆盖类级默认；标志需同步置位，否则只读不写
        self.persistence = SQLiteFlowPersistence(str(session_db or vibe_home / "sessions.db"))
        if hasattr(self, "_instance_persistence"):
            self._instance_persistence = True
        # VG-106：召回质量调优——相关度低于阈值的结果不注入 prompt
        self.recall_min_score = (
            recall_min_score
            if recall_min_score is not None
            else float(os.environ.get("VIBE_RECALL_MIN_SCORE", "0.35"))
        )
        # M3：CLI Runtime 绑定——换引擎不换大脑（ADR-0007）
        self.on_runtime_event: Any | None = None  # stdout 事件回调（REPL 流式打印）
        self.cli_workdir = Path(os.environ.get("VIBE_WORKDIR", os.getcwd())).resolve()
        self.cli_timeout = float(os.environ.get("VIBE_CLI_TIMEOUT", "600"))
        self.cli_runtime = cli_runtime
        if self.cli_runtime is None and getattr(soul, "runtime", "llm") not in ("llm", "", None):
            from .runtimes.registry import get_runtime

            self.cli_runtime = get_runtime(soul)

    @property
    def _memory_scope(self) -> str:
        return f"teammates/{self.soul.name.lower()}"

    def converse_turn(self) -> str:
        """覆盖内置闲聊路由：注入 Soul 身份与召回的记忆后再回复。"""
        user_message = self.state.current_user_message or ""
        if self.cli_runtime is not None:
            return self._turn_via_cli_runtime(user_message)
        return self._turn_via_llm(user_message)

    def _turn_via_llm(self, user_message: str) -> str:
        memories = self._recall(user_message)

        messages: list[LLMMessage] = [
            {"role": "system", "content": self._system_prompt(memories)},
            *self.conversation_messages,
        ]
        # BaseLLM 开启流式（stream_turn 才能逐字回传）；替身/自定义 LLM 直接调用
        if isinstance(self._llm, BaseLLM):
            with self._conversation_streaming_enabled(self._llm):
                response = self._llm.call(messages=messages)
        else:
            response = self._llm.call(messages=messages)
        content = response if isinstance(response, str) else str(response)

        self.append_assistant_message(content)
        self._remember_turn(user_message, content)
        return content

    def _turn_via_cli_runtime(self, user_message: str) -> str:
        """CLI 执行体路径（M3）：指令注入身份与记忆，产出落台账。"""
        assert self.cli_runtime is not None  # 类型收窄：入口已判定非空
        from .ledger import TaskLedger
        from .runtimes.base import TaskSpec
        from .runtimes.executor import run_with_retry

        memories = self._recall(user_message)
        instruction = self._system_prompt(memories) + f"\n\n# 用户指令\n{user_message}"
        spec = TaskSpec(
            instruction=instruction, workdir=self.cli_workdir, timeout_s=self.cli_timeout
        )
        ledger = TaskLedger(self.vibe_home / "ledger.db")
        try:
            content, _record = run_with_retry(
                spec, self.cli_runtime, ledger, attempts=1, on_event=self._forward_runtime_event
            )
        except Exception as exc:  # 门控拒绝/执行失败都不打断会话，明示原因
            content = f"⚠️ CLI 执行失败：{exc}"

        self.append_assistant_message(content)
        self._remember_turn(user_message, content)
        return content

    def _forward_runtime_event(self, event: Any) -> None:
        if self.on_runtime_event is not None:
            self.on_runtime_event(event)

    def _system_prompt(self, memories: list[str]) -> str:
        sections = [self.soul.identity_prompt()]
        if memories:
            recalled = "\n".join(f"- {m}" for m in memories)
            sections.append(f"# 长期记忆（与本次对话相关的历史沉淀）\n{recalled}")
        sections.append("用中文回复。")
        return "\n\n".join(s for s in sections if s)

    def _recall(self, query: str) -> list[str]:
        if self.memory_backend is None or not query:
            return []
        try:
            matches = self.memory_backend.recall(
                query=query,
                scope=self._memory_scope,
                limit=5,
                depth="shallow",
            )
        except Exception:
            # 记忆是增强项，不能因为它阻塞对话
            return []
        # VG-106 调优：阈值过滤 + 同记录去重 + 注入上限，抑制无关记忆混入 prompt
        seen: set[str] = set()
        contents: list[str] = []
        for m in matches:
            if m.score < self.recall_min_score or m.record.id in seen:
                continue
            seen.add(m.record.id)
            if m.record.content:
                contents.append(m.record.content)
            if len(contents) >= 3:
                break
        return contents

    def _remember_turn(self, user_message: str, reply: str) -> None:
        if self.memory_backend is None or not user_message:
            return
        # 记忆是增强项：写入失败（如网络/配额问题）不应打断对话
        with contextlib.suppress(Exception):
            self.memory_backend.remember(
                content=f"用户说：{user_message}\n{self.soul.name} 回复：{reply}",
                scope=self._memory_scope,
                categories=["conversation"],
                importance=0.4,
                source="chat",
            )

    def close(self) -> None:
        if self.memory_backend is not None:
            self.memory_backend.close()


def _default_llm(model: str) -> Any:
    # 兼容别名：历史调用点（测试/协作层）沿用此名，实现收拢到 llm_utils
    from .llm_utils import default_llm

    return default_llm(model)


def _build_memory(soul: Soul, vibe_home: Path) -> Memory | None:
    if not soul.memory_enabled or os.environ.get("VIBE_MEMORY", "true").lower() == "false":
        return None
    return Memory(
        llm=soul.model,
        storage=str(vibe_home / "memory"),
        root_scope="vibegoing",
    )


def build_admin_memory(vibe_home: Path) -> Memory:
    """管理用途的记忆后端：list/show/forget 不触发 LLM 与嵌入调用。"""
    return Memory(
        llm="openai/gpt-4o",
        storage=str(vibe_home / "memory"),
        root_scope="vibegoing",
    )
