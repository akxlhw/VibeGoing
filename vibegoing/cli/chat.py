"""对话命令（默认）：会话入口与流式 REPL。"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from uuid import uuid4

from ..session import SessionStore
from ..soul import Soul, SoulStore, default_soul
from ..teammate import TeammateFlow
from .common import home_arg


def add_chat_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--soul", default="ava", help="伙伴名字（默认 ava，不存在则按模板创建）")
    parser.add_argument(
        "--model",
        default=None,
        metavar="PROVIDER/MODEL",
        help="本次会话临时换模型（优先级高于 VIBE_LLM 与 Soul 绑定；Soul 与记忆不变）",
    )
    parser.add_argument("--list", action="store_true", help="列出所有伙伴后退出")
    parser.add_argument("--list-sessions", action="store_true", help="列出历史会话后退出")
    parser.add_argument(
        "--resume",
        nargs="?",
        const="",
        default=None,
        metavar="SESSION_ID",
        help="恢复会话：不带参数恢复最近一次，带 ID 支持唯一前缀",
    )


def prepare_soul(args: argparse.Namespace, store: SoulStore) -> Soul:
    """加载 Soul 并应用模型覆盖：--model > VIBE_LLM > Soul 绑定（VG-105）。"""
    soul = store.load_or_create(args.soul, template=default_soul())
    override = getattr(args, "model", None) or os.environ.get("VIBE_LLM")
    if override:
        soul = soul.model_copy(update={"model": override})
    return soul


def run_chat(args: argparse.Namespace) -> None:
    home = home_arg(args.home)
    store = SoulStore(home / "souls")
    session_store = SessionStore(home / "sessions.db")

    if args.list:
        names = store.list_names()
        print("\n".join(names) if names else "暂无伙伴（vibegoing soul create <名字> 创建）")
        return

    if args.list_sessions:
        sessions = session_store.list_sessions()
        if not sessions:
            print("暂无历史会话。")
            return
        print(f"{'会话 ID':<38} {'消息数':>4}  最近快照      首条消息")
        for s in sessions:
            print(f"{s.session_id:<38} {s.message_count:>4}  {s.updated_at[:19]}  {s.preview}")
        return

    soul = prepare_soul(args, store)

    session_id: str | None = None
    if args.resume is not None:
        session_id = session_store.resolve(args.resume or None)
        if session_id is None:
            sessions = session_store.list_sessions()
            print("找不到要恢复的会话。可用会话：")
            for s in sessions:
                print(f"  {s.session_id}  {s.updated_at[:19]}  {s.preview}")
            return
        print(f"↩️  恢复会话 {session_id}")
    else:
        session_id = str(uuid4())

    memory_flag = "开" if soul.memory_enabled else "关"
    runtime_name = getattr(soul, "runtime", "llm") or "llm"
    print(
        f"{soul.emoji} {soul.name} 已就绪"
        f"（模型：{soul.model}，执行体：{runtime_name}，记忆：{memory_flag}）"
    )
    print(f"会话 ID：{session_id}（之后可用 --resume {session_id} 继续）")
    print("输入 exit / quit 结束对话。\n")

    flow = TeammateFlow(soul=soul, vibe_home=home, session_db=home / "sessions.db")
    if flow.cli_runtime is not None:

        def _print_event(event) -> None:
            if event.kind == "stdout" and event.content:
                print(event.content, end="", flush=True)

        flow.on_runtime_event = _print_event
    try:
        run_repl(flow, session_id)
    finally:
        flow.finalize_session_traces()
        flow.close()


def run_repl(
    flow: TeammateFlow,
    session_id: str,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    chunk_writer: Callable[[str], None] | None = None,
) -> None:
    """流式 REPL：LLM 输出逐字打印；不支持流式的运行时回退为整段输出。"""
    write_chunk = chunk_writer or (lambda text: print(text, end="", flush=True))
    while True:
        try:
            message = input_fn("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            output_fn("")
            break
        if message.lower() in ("exit", "quit"):
            break
        if not message:
            continue

        stream = flow.stream_turn(message, session_id=session_id)
        streamed = False
        with stream:
            output_fn("")
            for frame in stream.events:
                if frame.channel == "llm" and frame.type == "llm_stream_chunk" and frame.content:
                    write_chunk(frame.content)
                    streamed = True
        if streamed:
            output_fn("")
        else:
            output_fn(f"Assistant: {stream.result}")
