"""crew 命令组：多伙伴协作（run/status/list，M2）。"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..ledger import TaskLedger
from ..soul import SoulStore, default_soul


def add_crew_arguments(sub: argparse._SubParsersAction) -> None:
    crew = sub.add_parser("crew", help="多伙伴协作（M2）")
    crew_sub = crew.add_subparsers(dest="crew_command", required=True)

    c_run = crew_sub.add_parser("run", help="运行协作任务：产出 → 复核 → 汇总（或层级派活）")
    c_run.add_argument("task", help="任务描述")
    c_run.add_argument(
        "--mode",
        choices=["review", "hierarchy"],
        default="review",
        help="协作模式：review=交叉复核（默认），hierarchy=管理者拆解分派",
    )
    c_run.add_argument("--producer", default=None, help="指定产出伙伴（默认按能力路由）")
    c_run.add_argument("--reviewer", default=None, help="指定复核伙伴（默认按能力路由）")
    c_run.add_argument("--manager", default=None, help="hierarchy 模式的管理者（默认第一位伙伴）")

    c_status = crew_sub.add_parser("status", help="查看任务台账（默认最近一件，ID 支持前缀）")
    c_status.add_argument("task_id", nargs="?", default=None)

    c_list = crew_sub.add_parser("list", help="列出协作任务")
    c_list.add_argument("--limit", type=int, default=20)


def run_crew(
    args: argparse.Namespace, home: Path, llm_factory: Callable[[str], Any] | None = None
) -> None:
    from ..collab.pipeline import run_hierarchy_pipeline, run_review_pipeline
    from ..collab.routing import pick_pair
    from ..soul import default_reviewer_soul
    from ..teammate import _build_memory

    cmd = args.crew_command
    ledger = TaskLedger(home / "ledger.db")

    if cmd == "list":
        tasks = ledger.list_tasks(args.limit)
        if not tasks:
            print('暂无协作任务（vibegoing crew run "任务描述" 开始）。')
            return
        print(f"{'ID':<10} {'模式':<10} {'状态':<8} 描述")
        for t in tasks:
            print(f"{t.task_id:<10} {t.mode:<10} {t.status:<8} {t.description[:40]}")
        return

    if cmd == "status":
        latest = ledger.list_tasks(1)
        task_id = args.task_id or (latest[0].task_id if latest else None)
        got = ledger.get(task_id) if task_id else None
        if got is None:
            print(f"找不到任务 {task_id or '(台账为空)'}（ID 支持前缀匹配）")
            return
        task, stages = got
        print(f"任务 {task.task_id}（{task.mode}）状态：{task.status}")
        print(f"描述：{task.description}")
        print(f"创建：{task.created_at}   更新：{task.updated_at}")
        for s in stages:
            print(f"\n── {s.stage} · {s.agent}（{s.created_at}）──")
            print(s.output)
        return

    # crew run
    store = SoulStore(home / "souls")
    store.load_or_create("ava", template=default_soul())
    souls = [store.load(name) for name in store.list_names()]

    def memory_for(soul):
        return _build_memory(soul, home)

    if args.mode == "hierarchy":
        manager_name = args.manager or souls[0].name
        manager = store.load(manager_name)
        record = run_hierarchy_pipeline(
            args.task,
            manager,
            souls,
            home,
            llm_factory=llm_factory,
            ledger=ledger,
            memory_for=memory_for,
        )
    else:
        producer = store.load(args.producer) if args.producer else None
        reviewer = store.load(args.reviewer) if args.reviewer else None
        if producer is None or reviewer is None:
            routed = pick_pair(args.task, souls)
            if routed is not None:
                producer = producer or routed[0]
                if reviewer is None and routed[1].name != producer.name:
                    reviewer = routed[1]
            if producer is None:
                producer = souls[0]
            if reviewer is None or reviewer.name == producer.name:
                fallback_name = "bob" if producer.name != "bob" else "carl"
                reviewer = store.load_or_create(fallback_name, template=default_reviewer_soul())
                print(
                    f"ℹ️  未指定/不可用复核者，已按模板准备复核伙伴 {reviewer.emoji} {reviewer.name}"
                )
        record = run_review_pipeline(
            args.task,
            producer,
            reviewer,
            home,
            llm_factory=llm_factory,
            ledger=ledger,
            memory_for=memory_for,
        )

    got = ledger.get(record.task_id)
    if got is not None:
        _, stages = got
        if stages:
            print(f"\n══ 最终结论（{stages[-1].stage} · {stages[-1].agent}）══")
            print(stages[-1].output)
