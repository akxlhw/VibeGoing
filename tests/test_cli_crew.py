"""M2 crew CLI：run/status/list 端到端（替身 LLM，无 Key）。"""

from __future__ import annotations

from collections.abc import Callable

import vibegoing.cli as cli
from vibegoing.collab.ledger import TaskLedger


class SequenceLLM:
    def __init__(self):
        self.n = 0

    def call(self, messages, **kwargs):
        self.n += 1
        return f"回复{self.n}"


class PlanThenRun:
    """hierarchy 用：第一次返回计划 JSON，其后顺序应答。"""

    def __init__(self):
        self.n = 0

    def call(self, messages, **kwargs):
        self.n += 1
        if self.n == 1:
            return (
                '{"steps": ['
                '{"stage": "调研", "agent": "ava", "instruction": "查资料"},'
                '{"stage": "写作", "agent": "bob", "instruction": "写摘要"}]}'
            )
        return f"阶段产出{self.n - 1}"


def _factory() -> Callable[[str], object]:
    state: dict[str, object] = {}

    def factory(model: str):
        return state.setdefault(model, SequenceLLM())

    return factory


def test_crew_run_review_out_of_box(tmp_path, capsys):
    """一条命令开箱跑通：自动补齐伙伴，产出→复核→汇总落台账。"""
    cli._run_crew(
        _args("run", task="调研多智能体框架并写摘要", mode="review"),
        tmp_path,
        llm_factory=_factory(),
    )
    out = capsys.readouterr().out
    assert "交叉复核开始" in out
    assert "最终结论" in out
    assert "bob" in out  # 自动创建了复核伙伴

    ledger = TaskLedger(tmp_path / "ledger.db")
    task = ledger.list_tasks()[0]
    assert task.status == "done" and task.mode == "review"
    _, stages = ledger.get(task.task_id) or (None, [])
    assert [s.stage for s in stages] == ["produce", "review", "finalize"]


def test_crew_run_hierarchy(tmp_path, capsys):
    from vibegoing.soul import SoulStore, default_reviewer_soul

    SoulStore(tmp_path / "souls").load_or_create("bob", template=default_reviewer_soul())

    cli._run_crew(
        _args("run", task="做一份行业速览", mode="hierarchy"),
        tmp_path,
        llm_factory=lambda model: PlanThenRun(),
    )
    out = capsys.readouterr().out
    assert "计划就绪" in out and "层级派活完成" in out

    ledger = TaskLedger(tmp_path / "ledger.db")
    _, stages = ledger.get(ledger.list_tasks()[0].task_id) or (None, [])
    assert [(s.stage, s.agent) for s in stages] == [("调研", "ava"), ("写作", "bob")]


def test_crew_status_and_list(tmp_path, capsys):
    cli._run_crew(
        _args("run", task="任务A", mode="review"),
        tmp_path,
        llm_factory=_factory(),
    )
    capsys.readouterr()

    cli._run_crew(_args("list"), tmp_path)
    out = capsys.readouterr().out
    assert "review" in out and "done" in out and "任务A" in out

    cli._run_crew(_args("status"), tmp_path)  # 默认最近一件
    out = capsys.readouterr().out
    assert "状态：done" in out and "produce" in out and "finalize" in out


def test_crew_status_not_found(tmp_path, capsys):
    cli._run_crew(_args("status", task_id="zzz"), tmp_path)
    assert "找不到任务" in capsys.readouterr().out


def _args(crew_command: str, **kwargs):
    import argparse

    namespace = argparse.Namespace(crew_command=crew_command)
    for key, value in kwargs.items():
        setattr(namespace, key, value)
    # 对齐真实 argparse 的默认值
    namespace.task_id = kwargs.get("task_id")
    namespace.limit = kwargs.get("limit", 20)
    namespace.producer = kwargs.get("producer")
    namespace.reviewer = kwargs.get("reviewer")
    namespace.manager = kwargs.get("manager")
    return namespace
