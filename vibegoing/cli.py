"""命令行入口：对话（默认）与 soul/memory 子命令组。

结构：
  vibegoing                       # 与伙伴对话（--soul/--resume/--list-sessions）
  vibegoing soul list|show|create|edit
  vibegoing memory list|show|forget   # VG-103
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from .session import SessionStore
from .soul import Soul, SoulStore, default_soul
from .teammate import TeammateFlow, build_admin_memory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vibegoing",
        description="与你的本地 AI 伙伴对话（基于 CrewAI 的会话型 Flow）",
    )
    parser.add_argument("--home", default=None, help="数据目录（默认取 VIBE_HOME 或 ./.vibe）")
    _add_chat_arguments(parser)

    sub = parser.add_subparsers(dest="command")

    # 注意：--home 只在根解析器定义（子命令叶子重复定义会用默认值覆盖根值）
    soul = sub.add_parser("soul", help="伙伴身份管理")
    soul_sub = soul.add_subparsers(dest="soul_command", required=True)

    soul_sub.add_parser("list", help="列出所有伙伴")

    p_show = soul_sub.add_parser("show", help="查看伙伴完整 Soul")
    p_show.add_argument("name")

    p_create = soul_sub.add_parser("create", help="创建伙伴")
    p_create.add_argument("name")
    p_create.add_argument("--emoji", default="🤖")
    p_create.add_argument("--persona", default=None, help="人设描述（与 --ai 二选一）")
    p_create.add_argument(
        "--ai", default=None, metavar="DESC", help="用 LLM 按一句话描述生成人设（需 API Key）"
    )
    p_create.add_argument("--model", default="openai/gpt-4o")
    p_create.add_argument(
        "--principles", default=None, help='工作原则，逗号分隔，如 "先给结论,不带情绪"'
    )
    p_create.add_argument(
        "--capabilities", default=None, help='能力标签，逗号分隔，如 "调研,写作"（协作路由用）'
    )

    p_edit = soul_sub.add_parser("edit", help="编辑伙伴字段（只改传入的项）")
    p_edit.add_argument("name")
    p_edit.add_argument("--emoji")
    p_edit.add_argument("--persona")
    p_edit.add_argument("--model")
    p_edit.add_argument("--principles", help="工作原则，逗号分隔（整体替换）")
    p_edit.add_argument("--capabilities", help="能力标签，逗号分隔（整体替换）")
    p_edit.add_argument(
        "--memory", action=argparse.BooleanOptionalAction, default=None, help="开/关长期记忆"
    )

    memory = sub.add_parser("memory", help="长期记忆管理")
    mem_sub = memory.add_subparsers(dest="memory_command", required=True)

    m_list = mem_sub.add_parser("list", help="列出记忆记录（默认全部，--soul 限定伙伴）")
    m_list.add_argument("--soul", default=None, help="只看该伙伴的记忆")
    m_list.add_argument("--limit", type=int, default=20)

    m_show = mem_sub.add_parser("show", help="查看一条记忆的完整内容")
    m_show.add_argument("record_id")

    m_forget = mem_sub.add_parser("forget", help="按记录 ID 删除记忆（可多个）")
    m_forget.add_argument("record_ids", nargs="+")

    return parser


def _add_chat_arguments(parser: argparse.ArgumentParser) -> None:
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


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    args = build_parser().parse_args(argv)

    if args.command == "soul":
        home = _home_arg(args.home)
        _run_soul(args, SoulStore(home / "souls"))
        return
    if args.command == "memory":
        _run_memory(args, _home_arg(args.home))
        return
    _run_chat(args)


def _home_arg(value: str | None) -> Path:
    return Path(value or os.environ.get("VIBE_HOME", "./.vibe")).expanduser().resolve()


# ---- soul 子命令 ----


def _run_soul(args: argparse.Namespace, store: SoulStore) -> None:
    cmd = args.soul_command
    if cmd == "list":
        names = store.list_names()
        print("\n".join(names) if names else "暂无伙伴（vibegoing soul create <名字> 创建）")
    elif cmd == "show":
        _print_soul(store.load(args.name))
    elif cmd == "create":
        _soul_create(args, store)
    elif cmd == "edit":
        _soul_edit(args, store)


def _soul_create(args: argparse.Namespace, store: SoulStore) -> None:
    if store.exists(args.name):
        print(f"伙伴 {args.name} 已存在：{store.path_for(args.name)}")
        return
    persona = args.persona
    principles = _parse_principles(args.principles)
    if persona is None and args.ai:
        try:
            persona, ai_principles = _ai_persona(args.ai, args.model)
            principles = principles or ai_principles
        except Exception as exc:  # LLM 调用失败给出可行动的错误
            print(f"AI 生成人设失败（{exc}）。请配置 API Key 或改用 --persona 手工指定。")
            return
    soul = Soul(
        name=args.name,
        emoji=args.emoji,
        persona=persona or "",
        principles=principles,
        model=args.model,
        capabilities=_parse_principles(args.capabilities),
    )
    path = store.save(soul)
    print(f"已创建 {soul.emoji} {soul.name} → {path}")
    _print_soul(soul)


def _soul_edit(args: argparse.Namespace, store: SoulStore) -> None:
    soul = store.load(args.name)
    updates: dict[str, object] = {}
    if args.emoji is not None:
        updates["emoji"] = args.emoji
    if args.persona is not None:
        updates["persona"] = args.persona
    if args.model is not None:
        updates["model"] = args.model
    if args.principles is not None:
        updates["principles"] = _parse_principles(args.principles)
    if getattr(args, "capabilities", None) is not None:
        updates["capabilities"] = _parse_principles(args.capabilities)
    if args.memory is not None:
        updates["memory_enabled"] = args.memory
    if not updates:
        print("未指定任何修改项（--emoji/--persona/--model/--principles/--memory）")
        return
    soul = soul.model_copy(update=updates)
    store.save(soul)
    print(f"已更新 {soul.name}：{', '.join(updates)}")
    _print_soul(soul)


def _print_soul(soul: Soul) -> None:
    memory_flag = "开" if soul.memory_enabled else "关"
    print(f"{soul.emoji} {soul.name}（模型：{soul.model}，记忆：{memory_flag}）")
    if soul.persona:
        print(f"  人设：{soul.persona}")
    if soul.principles:
        print(f"  原则：{'；'.join(soul.principles)}")
    if soul.capabilities:
        print(f"  能力：{'、'.join(soul.capabilities)}")


def _parse_principles(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _ai_persona(description: str, model: str) -> tuple[str, list[str]]:
    """用 LLM 依一句话描述生成人设与原则（VG-102 --ai）。"""
    from .teammate import _default_llm

    llm = _default_llm(model)
    prompt = (
        "你是人设设计师。根据描述为一位 AI 伙伴撰写人设。"
        '只输出 JSON：{"persona": "第二人称人设，100字内", '
        '"principles": ["3 条工作原则"]}\n'
        f"描述：{description}"
    )
    raw = llm.call(messages=[{"role": "user", "content": prompt}])
    with contextlib.suppress(json.JSONDecodeError):
        data = json.loads(raw if isinstance(raw, str) else str(raw))
        if isinstance(data, dict) and "persona" in data:
            return str(data["persona"]), [str(p) for p in data.get("principles", [])]
    # 模型未按 JSON 输出时，整段作为人设
    return (raw if isinstance(raw, str) else str(raw)).strip(), []


# ---- memory 子命令（VG-103）----


def _run_memory(args: argparse.Namespace, home: Path) -> None:
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


# ---- 对话（默认命令） ----


def _prepare_soul(args: argparse.Namespace, store: SoulStore) -> Soul:
    """加载 Soul 并应用模型覆盖：--model > VIBE_LLM > Soul 绑定（VG-105）。"""
    soul = store.load_or_create(args.soul, template=default_soul())
    override = getattr(args, "model", None) or os.environ.get("VIBE_LLM")
    if override:
        soul = soul.model_copy(update={"model": override})
    return soul


def _run_chat(args: argparse.Namespace) -> None:
    home = _home_arg(args.home)
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

    soul = _prepare_soul(args, store)

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
    print(f"{soul.emoji} {soul.name} 已就绪（模型：{soul.model}，记忆：{memory_flag}）")
    print(f"会话 ID：{session_id}（之后可用 --resume {session_id} 继续）")
    print("输入 exit / quit 结束对话。\n")

    flow = TeammateFlow(soul=soul, vibe_home=home, session_db=home / "sessions.db")
    try:
        _run_repl(flow, session_id)
    finally:
        flow.finalize_session_traces()
        flow.close()


def _run_repl(
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
