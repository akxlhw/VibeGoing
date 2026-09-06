"""VG-201/VG-202 编排管线：交叉复核与层级派活（替身 LLM 全链路）。"""

from __future__ import annotations

import pytest

from vibegoing.collab.ledger import TaskLedger
from vibegoing.collab.pipeline import (
    plan_with_manager,
    run_hierarchy_pipeline,
    run_review_pipeline,
)
from vibegoing.soul import Soul


class RecordingLLM:
    """替身 LLM：按预设序列出回复，并记录每次调用的消息。"""

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def call(self, messages, **kwargs):
        self.calls.append({"messages": messages})
        return self.replies.pop(0)


def _souls():
    producer = Soul(name="researcher", persona="调研员", capabilities=["调研"])
    reviewer = Soul(name="writer", persona="复核员", capabilities=["写作"])
    return producer, reviewer


def test_review_pipeline_three_stages_in_ledger(tmp_path):
    producer, reviewer = _souls()
    ledger = TaskLedger(tmp_path / "ledger.db")
    progress: list[str] = []
    # 单个替身按调用顺序依次应答：产出 → 复核 → 终稿
    stub = RecordingLLM(["初稿：三条发现", "复核：补风险", "终稿：摘要"])

    record = run_review_pipeline(
        "调研多智能体框架并写摘要",
        producer,
        reviewer,
        vibe_home=tmp_path,
        llm_factory=lambda model: stub,
        ledger=ledger,
        announce=progress.append,
    )

    assert record.status == "done"
    _, stages = ledger.get(record.task_id) or (None, [])
    assert [(s.stage, s.agent) for s in stages] == [
        ("produce", "researcher"),
        ("review", "writer"),
        ("finalize", "researcher"),
    ]
    assert stages[2].output == "终稿：摘要"
    # 进展实时可见
    joined = "\n".join(progress)
    assert "阶段 1/3 产出" in joined and "阶段 2/3 复核" in joined
    assert "交叉复核完成" in joined


def test_review_pipeline_handoff_carries_draft(tmp_path):
    producer, reviewer = _souls()
    ledger = TaskLedger(tmp_path / "ledger.db")
    stubs: dict[str, RecordingLLM] = {}

    def factory(model):
        key = "producer" if model == producer.model else "reviewer"
        stubs.setdefault(key, RecordingLLM(["初稿内容 ABC", key + "-复核", "终稿"]))
        return stubs[key]

    # 用不同模型保证两个伙伴拿到不同替身
    producer = producer.model_copy(update={"model": "openai/gpt-4o"})
    reviewer = reviewer.model_copy(update={"model": "deepseek/deepseek-chat"})

    run_review_pipeline(
        "任务X",
        producer,
        reviewer,
        vibe_home=tmp_path,
        llm_factory=factory,
        ledger=ledger,
        announce=lambda s: None,
    )

    reviewer_prompt = stubs["reviewer"].calls[0]["messages"][-1]["content"]
    assert "初稿内容 ABC" in reviewer_prompt  # 复核方收到了产出方的交接内容
    assert "严格复核" in reviewer_prompt
    # 身份注入：复核方 system prompt 是复核员的人设
    system = stubs["reviewer"].calls[0]["messages"][0]["content"]
    assert "复核员" in system


def test_review_pipeline_failure_marks_task_failed(tmp_path):
    producer, reviewer = _souls()
    ledger = TaskLedger(tmp_path / "ledger.db")

    class BoomLLM:
        def call(self, messages, **kwargs):
            raise RuntimeError("api down")

    with pytest.raises(RuntimeError, match="api down"):
        run_review_pipeline(
            "任务",
            producer,
            reviewer,
            vibe_home=tmp_path,
            llm_factory=lambda m: BoomLLM(),
            ledger=ledger,
            announce=lambda s: None,
        )

    got = ledger.list_tasks()[0]
    assert got.status == "failed"


def test_manager_plan_parses_and_validates():
    manager = Soul(name="boss", persona="管理者")
    agents = [
        Soul(name="researcher", capabilities=["调研"]),
        Soul(name="writer", capabilities=["写作"]),
    ]
    llm = RecordingLLM(
        [
            '{"steps": ['
            '{"stage": "调研", "agent": "researcher", "instruction": "查资料"},'
            '{"stage": "写作", "agent": "writer", "instruction": "写摘要"}]}'
        ]
    )
    steps = plan_with_manager("任务", manager, agents, llm)
    assert [s.agent for s in steps] == ["researcher", "writer"]

    # 指派了名单外伙伴 → 兜底单步
    llm_bad = RecordingLLM(['{"steps": [{"stage": "x", "agent": "ghost", "instruction": "?"}]}'])
    fallback = plan_with_manager("任务", manager, agents, llm_bad)
    assert len(fallback) == 1 and fallback[0].agent == "researcher"


def test_hierarchy_pipeline_executes_plan_with_accumulated_context(tmp_path):
    manager = Soul(name="boss", persona="管理者", model="manager/model")
    agents = [
        Soul(name="researcher", capabilities=["调研"], model="a/model"),
        Soul(name="writer", capabilities=["写作"], model="b/model"),
    ]
    ledger = TaskLedger(tmp_path / "ledger.db")
    progress: list[str] = []
    stubs: dict[str, RecordingLLM] = {}

    def factory(model: str):
        if model == "manager/model":
            return RecordingLLM(
                [
                    '{"steps": ['
                    '{"stage": "调研", "agent": "researcher", "instruction": "查资料"},'
                    '{"stage": "写作", "agent": "writer", "instruction": "写摘要"}]}'
                ]
            )
        stubs.setdefault(model, RecordingLLM(["上游产出内容", "最终摘要"]))
        return stubs[model]

    record = run_hierarchy_pipeline(
        "做一份行业速览",
        manager,
        agents,
        vibe_home=tmp_path,
        llm_factory=factory,
        ledger=ledger,
        announce=progress.append,
    )

    assert record.status == "done"
    _, stages = ledger.get(record.task_id) or (None, [])
    assert [(s.stage, s.agent) for s in stages] == [
        ("调研", "researcher"),
        ("写作", "writer"),
    ]
    # 第二阶段的提示词包含第一阶段的产出（交接累积）
    writer_prompt = stubs["b/model"].calls[0]["messages"][-1]["content"]
    assert "上游产出内容" in writer_prompt
    assert "第 2/2 阶段" in writer_prompt
    assert "计划就绪" in "\n".join(progress)
