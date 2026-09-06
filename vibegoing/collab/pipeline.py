"""编排管线（VG-201 交叉复核 / VG-202 层级派活）。

自研轻量编排（决策与理由见 ADR-0006）：按阶段直接调用伙伴的 LLM，
阶段间以 HandoffPacket 传递上下文，产物落 TaskLedger，进展经 announce 实时输出。
每个阶段的提示词注入 Soul 身份；记忆召回/沉淀经 memory_for 钩子接入（可选）。
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from crewai.utilities.types import LLMMessage

from ..soul import Soul
from ..teammate import _default_llm
from .handoff import HandoffPacket
from .ledger import TaskLedger, TaskRecord

# 阶段执行结果回调：接到进展信息就实时展示（CLI 为 print，测试可注入）
Announce = Callable[[str], None]
# 模型 → LLM 实例的工厂（测试注入替身；默认用 CrewAI LLM）
LLMFactory = Callable[[str], Any]
# 伙伴 → 记忆后端的钩子（无记忆/无 Key 时返回 None）
MemoryHook = Callable[[Soul], Any]


@dataclass
class PlanStep:
    """层级派活模式中管理者拆解出的一个阶段。"""

    stage: str
    agent: str
    instruction: str


@dataclass
class _StageContext:
    """跨阶段累积的执行上下文。"""

    prior_outputs: list[dict[str, str]] = field(default_factory=list)


def _stage_messages(soul: Soul, instruction: str, memories: list[str]) -> list[LLMMessage]:
    system = soul.identity_prompt()
    if memories:
        recalled = "\n".join(f"- {m}" for m in memories)
        system += f"\n\n# 长期记忆（相关沉淀）\n{recalled}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": instruction},
    ]


def _run_stage(
    soul: Soul,
    llm: Any,
    instruction: str,
    memory: Any = None,
    memory_scope: str | None = None,
) -> str:
    memories: list[str] = []
    if memory is not None and memory_scope:
        with contextlib.suppress(Exception):
            matches = memory.recall(query=instruction, scope=memory_scope, limit=3, depth="shallow")
            memories = [m.record.content for m in matches if m.record.content]
    response = llm.call(messages=_stage_messages(soul, instruction, memories))
    content = response if isinstance(response, str) else str(response)
    if memory is not None and memory_scope:
        with contextlib.suppress(Exception):
            memory.remember(
                content=instruction,
                scope=memory_scope,
                categories=["collaboration"],
                importance=0.4,
                source="crew",
            )
    return content


def _soul_memory_scope(soul: Soul) -> str:
    return f"teammates/{soul.name.lower()}"


def run_review_pipeline(
    task: str,
    producer: Soul,
    reviewer: Soul,
    vibe_home: Path,
    llm_factory: LLMFactory | None = None,
    ledger: TaskLedger | None = None,
    memory_for: MemoryHook | None = None,
    announce: Announce = print,
) -> TaskRecord:
    """交叉复核（VG-201）：产出 → 复核 → 汇总交付。

    产出与复核用不同伙伴（建议不同模型），降低单模型偏差。
    """
    ledger = ledger or TaskLedger(vibe_home / "ledger.db")
    factory = llm_factory or _default_llm
    record = ledger.create_task(task, mode="review")
    ledger.set_status(record.task_id, "running")
    announce(f"[{record.task_id}] ▶ 交叉复核开始：{producer.name} 产出 → {reviewer.name} 复核")

    try:
        producer_llm = factory(producer.model)
        reviewer_llm = factory(reviewer.model)
        producer_memory = memory_for(producer) if memory_for else None
        reviewer_memory = memory_for(reviewer) if memory_for else None

        announce(f"[{record.task_id}] ▶ 阶段 1/3 产出 · {producer.name}")
        draft = _run_stage(
            producer,
            producer_llm,
            f"完成任务：{task}",
            producer_memory,
            _soul_memory_scope(producer),
        )
        ledger.add_stage(record.task_id, "produce", producer.name, draft)
        announce(f"[{record.task_id}] ✔ 产出完成（{len(draft)} 字）")

        review_packet = HandoffPacket(
            task=task,
            from_agent=producer.name,
            to_agent=reviewer.name,
            prior_outputs=[{"source": f"{producer.name}/produce", "output": draft}],
            expectations="严格复核：指出事实错误、遗漏与风险，给出具体修改建议",
        )
        announce(f"[{record.task_id}] ▶ 阶段 2/3 复核 · {reviewer.name}")
        review = _run_stage(
            reviewer,
            reviewer_llm,
            review_packet.to_prompt(),
            reviewer_memory,
            _soul_memory_scope(reviewer),
        )
        ledger.add_stage(record.task_id, "review", reviewer.name, review)
        announce(f"[{record.task_id}] ✔ 复核完成（{len(review)} 字）")

        finalize_packet = HandoffPacket(
            task=task,
            from_agent=reviewer.name,
            to_agent=producer.name,
            prior_outputs=[
                {"source": f"{producer.name}/produce", "output": draft},
                {"source": f"{reviewer.name}/review", "output": review},
            ],
            expectations="按复核意见修订，交付最终结果",
        )
        announce(f"[{record.task_id}] ▶ 阶段 3/3 汇总 · {producer.name}")
        final = _run_stage(
            producer,
            producer_llm,
            finalize_packet.to_prompt(),
            producer_memory,
            _soul_memory_scope(producer),
        )
        ledger.add_stage(record.task_id, "finalize", producer.name, final)

        record = ledger.set_status(record.task_id, "done")
        announce(f"[{record.task_id}] ✔ 交叉复核完成，最终结论已落台账")
    except Exception as exc:
        ledger.set_status(record.task_id, "failed")
        announce(f"[{record.task_id}] ✘ 失败：{exc}")
        raise
    return record


def plan_with_manager(task: str, manager: Soul, agents: list[Soul], llm: Any) -> list[PlanStep]:
    """层级派活的计划阶段（VG-202）：管理者把任务拆解为带指派的阶段计划。

    返回 2~4 步；解析失败时退化为单步全任务（指派第一位伙伴）。
    """
    roster = "、".join(f"{s.name}（能力：{'、'.join(s.capabilities) or '通用'}）" for s in agents)
    prompt = (
        f"你是团队管理者 {manager.name}，负责拆解并分派任务。\n"
        f"任务：{task}\n可用伙伴：{roster}\n"
        "把任务拆解为 2-4 个依次执行的阶段，每阶段指派给最合适的伙伴。"
        '只输出 JSON：{"steps": [{"stage": "阶段名", "agent": "伙伴名", '
        '"instruction": "给该伙伴的完整指令"}]}'
    )
    raw = llm.call(messages=_stage_messages(manager, prompt, []))
    text = raw if isinstance(raw, str) else str(raw)
    with contextlib.suppress(json.JSONDecodeError):
        data = json.loads(text)
        steps = [
            PlanStep(
                stage=str(s.get("stage", f"step{i}")),
                agent=str(s.get("agent", "")),
                instruction=str(s.get("instruction", "")),
            )
            for i, s in enumerate(data.get("steps", []))
            if s.get("agent") and s.get("instruction")
        ]
        names = {s.name for s in agents}
        if 2 <= len(steps) <= 4 and all(s.agent in names for s in steps):
            return steps
    # 计划不可用 → 单步兜底
    fallback_agent = agents[0].name if agents else manager.name
    return [PlanStep(stage="execute", agent=fallback_agent, instruction=f"完成任务：{task}")]


def run_hierarchy_pipeline(
    task: str,
    manager: Soul,
    agents: list[Soul],
    vibe_home: Path,
    llm_factory: LLMFactory | None = None,
    ledger: TaskLedger | None = None,
    memory_for: MemoryHook | None = None,
    announce: Announce = print,
) -> TaskRecord:
    """层级派活（VG-202）：管理者拆解 → 依计划顺序执行，交接累积上下文。"""
    ledger = ledger or TaskLedger(vibe_home / "ledger.db")
    factory = llm_factory or _default_llm
    record = ledger.create_task(task, mode="hierarchy")
    ledger.set_status(record.task_id, "running")

    try:
        manager_llm = factory(manager.model)
        steps = plan_with_manager(task, manager, agents, manager_llm)
        announce(f"[{record.task_id}] ▶ 计划就绪：{' → '.join(s.agent for s in steps)}")

        by_name = {s.name: s for s in agents}
        context = _StageContext()
        for i, step in enumerate(steps, 1):
            soul = by_name.get(step.agent)
            if soul is None:
                soul = manager if step.agent == manager.name else agents[0]
            memory = memory_for(soul) if memory_for else None
            packet = HandoffPacket(
                task=task,
                from_agent=manager.name,
                to_agent=soul.name,
                context=f"这是团队计划的第 {i}/{len(steps)} 阶段：{step.stage}",
                prior_outputs=list(context.prior_outputs),
                expectations=step.instruction,
            )
            announce(f"[{record.task_id}] ▶ 阶段 {i}/{len(steps)} {step.stage} · {soul.name}")
            output = _run_stage(
                soul,
                factory(soul.model),
                packet.to_prompt(),
                memory,
                _soul_memory_scope(soul),
            )
            ledger.add_stage(record.task_id, step.stage, soul.name, output)
            context.prior_outputs.append({"source": f"{soul.name}/{step.stage}", "output": output})
            announce(f"[{record.task_id}] ✔ {step.stage} 完成（{len(output)} 字）")

        record = ledger.set_status(record.task_id, "done")
        announce(f"[{record.task_id}] ✔ 层级派活完成，最终结论已落台账")
    except Exception as exc:
        ledger.set_status(record.task_id, "failed")
        announce(f"[{record.task_id}] ✘ 失败：{exc}")
        raise
    return record
