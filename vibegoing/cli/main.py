"""解析器聚合与命令分发。

结构：
  vibegoing                       # 与伙伴对话（--soul/--resume/--list-sessions）
  vibegoing soul list|show|create|edit      → soul_cmd.py
  vibegoing memory list|show|forget         → memory_cmd.py
  vibegoing crew run|status|list            → crew_cmd.py
  vibegoing runtime list|check              → runtime_cmd.py
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from ..soul import SoulStore
from .chat import add_chat_arguments, run_chat
from .common import home_arg
from .crew_cmd import add_crew_arguments, run_crew
from .memory_cmd import add_memory_arguments, run_memory
from .runtime_cmd import add_runtime_arguments, run_runtime
from .soul_cmd import add_soul_arguments, run_soul
from .ui_cmd import add_ui_arguments, run_ui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vibegoing",
        description="与你的本地 AI 伙伴对话（基于 CrewAI 的会话型 Flow）",
    )
    # 注意：--home 只在根解析器定义（子命令叶子重复定义会用默认值覆盖根值）
    parser.add_argument("--home", default=None, help="数据目录（默认取 VIBE_HOME 或 ./.vibe）")
    add_chat_arguments(parser)

    sub = parser.add_subparsers(dest="command")
    add_soul_arguments(sub)
    add_memory_arguments(sub)
    add_crew_arguments(sub)
    add_runtime_arguments(sub)
    add_ui_arguments(sub)
    return parser


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    args = build_parser().parse_args(argv)

    if args.command == "soul":
        home = home_arg(args.home)
        run_soul(args, SoulStore(home / "souls"))
        return
    if args.command == "memory":
        run_memory(args, home_arg(args.home))
        return
    if args.command == "crew":
        run_crew(args, home_arg(args.home))
        return
    if args.command == "runtime":
        run_runtime(args)
        return
    if args.command == "ui":
        run_ui(args)
        return
    run_chat(args)
