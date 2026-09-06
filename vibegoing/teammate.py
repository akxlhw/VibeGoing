"""会话型伙伴：把 Soul 人设与长期记忆注入每一轮对话。

基于 CrewAI 的 conversational Flow：每条用户消息是一轮 handle_turn，
伙伴的回复经由统一 Memory 做长期记忆的召回与沉淀。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from crewai.flow import ConversationConfig, ConversationState, Flow
from crewai.memory import Memory

from .soul import Soul


@ConversationConfig(defer_trace_finalization=True)
class TeammateFlow(Flow[ConversationState]):
    """一位常驻伙伴：turn 开始前召回记忆，turn 结束后沉淀记忆。"""

    def __init__(
        self,
        soul: Soul,
        vibe_home: Path,
        llm: Any | None = None,
        memory: Memory | None = None,
    ):
        super().__init__()
        self.soul = soul
        self._llm = llm if llm is not None else _default_llm(soul.model)
        self.memory = memory if memory is not None else _build_memory(soul, vibe_home)

    @property
    def _memory_scope(self) -> str:
        return f"teammates/{self.soul.name.lower()}"

    def converse_turn(self) -> str:
        """覆盖内置闲聊路由：注入 Soul 身份与召回的记忆后再回复。"""
        user_message = self.state.current_user_message or ""
        memories = self._recall(user_message)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt(memories)},
            *self.conversation_messages,
        ]
        response = self._llm.call(messages=messages)
        content = response if isinstance(response, str) else str(response)

        self.append_assistant_message(content)
        self._remember_turn(user_message, content)
        return content

    def _system_prompt(self, memories: list[str]) -> str:
        sections = [self.soul.identity_prompt()]
        if memories:
            recalled = "\n".join(f"- {m}" for m in memories)
            sections.append(f"# 长期记忆（与本次对话相关的历史沉淀）\n{recalled}")
        sections.append("用中文回复。")
        return "\n\n".join(s for s in sections if s)

    def _recall(self, query: str) -> list[str]:
        if self.memory is None or not query:
            return []
        try:
            matches = self.memory.recall(
                query=query,
                scope=self._memory_scope,
                limit=5,
                depth="shallow",
            )
            return [m.record.content for m in matches if m.record.content]
        except Exception:
            # 记忆是增强项，不能因为它阻塞对话
            return []

    def _remember_turn(self, user_message: str, reply: str) -> None:
        if self.memory is None or not user_message:
            return
        try:
            self.memory.remember(
                content=f"用户说：{user_message}\nAva 回复：{reply}",
                scope=self._memory_scope,
                categories=["conversation"],
                importance=0.4,
                source="chat",
            )
        except Exception:
            pass

    def close(self) -> None:
        if self.memory is not None:
            self.memory.close()


def _default_llm(model: str) -> Any:
    from crewai import LLM

    return LLM(model=model)


def _build_memory(soul: Soul, vibe_home: Path) -> Memory | None:
    if not soul.memory_enabled or os.environ.get("VIBE_MEMORY", "true").lower() == "false":
        return None
    return Memory(
        llm=soul.model,
        storage=str(vibe_home / "memory"),
        root_scope="vibegoing",
    )
