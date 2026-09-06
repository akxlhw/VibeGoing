"""memory 命令组：长期记忆管理（list/show/forget，VG-103）。"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..teammate import build_admin_memory


def add_memory_arguments(sub: argparse._SubParsersAction) -> None:
    memory = sub.add_parser("memory", help="长期记忆管理")
    mem_sub = memory.add_subparsers(dest="memory_command", required=True)

    m_list = mem_sub.add_parser("list", help="列出记忆记录（默认全部，--soul 限定伙伴）")
    m_list.add_argument("--soul", default=None, help="只看该伙伴的记忆")
    m_list.add_argument("--limit", type=int, default=20)

    m_show = mem_sub.add_parser("show", help="查看一条记忆的完整内容")
    m_show.add_argument("record_id")

    m_forget = mem_sub.add_parser("forget", help="按记录 ID 删除记忆（可多个）")
    m_forget.add_argument("record_ids", nargs="+")


def run_memory(args: argparse.Namespace, home: Path) -> None:
    memory = build_admin_memory(home)
    scope = f"teammates/{args.soul.lower()}" if getattr(args, "soul", None) else None
    cmd = args.memory_command

    if cmd == "list":
        records = memory.list_records(scope=scope, limit=args.limit)
        if not records:
            print("暂无记忆记录。")
            return
        print(f"{'ID':<10} {'类别':<16} 内容")
        for r in records:
            cats = ",".join(r.categories) or "-"
            print(f"{r.id[:8]:<10} {cats:<16} {r.content[:60]}")
    elif cmd == "show":
        records = memory.list_records(scope=scope, limit=200)
        match = next((r for r in records if r.id.startswith(args.record_id)), None)
        if match is None:
            print(f"找不到记忆 {args.record_id}（ID 支持前缀匹配）")
            return
        print(f"ID：{match.id}")
        print(f"Scope：{match.scope}   类别：{','.join(match.categories) or '-'}")
        print(f"内容：\n{match.content}")
    elif cmd == "forget":
        deleted = memory.forget(record_ids=args.record_ids)
        print(f"已遗忘 {deleted} 条记忆。")
