"""runtime 命令组：执行体健康检查（list/check，M3）。"""

from __future__ import annotations

import argparse


def add_runtime_arguments(sub: argparse._SubParsersAction) -> None:
    from ..runtimes.registry import runtime_names

    runtime = sub.add_parser("runtime", help="执行体管理（M3）")
    runtime_sub = runtime.add_subparsers(dest="runtime_command", required=True)
    runtime_sub.add_parser("list", help="列出全部执行体与健康状态")
    rt_check = runtime_sub.add_parser("check", help="检查单个执行体")
    rt_check.add_argument("name", choices=runtime_names())


def run_runtime(args: argparse.Namespace) -> None:
    from ..runtimes.registry import get_runtime, runtime_names
    from ..soul import Soul

    names = runtime_names()
    if args.runtime_command == "check":
        names = [args.name]
    for name in names:
        runtime = get_runtime(Soul(name="probe", runtime=name))
        health = runtime.health()
        flag = "✅" if health.ok else "❌"
        print(f"{flag} {name:<12} {health.detail}")
        if health.ok and health.version:
            print(f"   版本：{health.version}")
