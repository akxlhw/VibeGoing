"""soul 命令组：伙伴身份管理（list/show/create/edit）。"""

from __future__ import annotations

import argparse
import contextlib
import json

from ..soul import Soul, SoulStore
from .common import parse_tags, print_soul


def add_soul_arguments(sub: argparse._SubParsersAction) -> None:
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
    from ..runtimes.registry import runtime_names

    p_create.add_argument(
        "--runtime",
        choices=runtime_names(),
        default="llm",
        help="执行体绑定（默认 llm；如 zcode/kimi-code/deepseek-harness/claude-code/codex）",
    )

    p_edit = soul_sub.add_parser("edit", help="编辑伙伴字段（只改传入的项）")
    p_edit.add_argument("name")
    p_edit.add_argument("--emoji")
    p_edit.add_argument("--persona")
    p_edit.add_argument("--model")
    p_edit.add_argument("--principles", help="工作原则，逗号分隔（整体替换）")
    p_edit.add_argument("--capabilities", help="能力标签，逗号分隔（整体替换）")
    p_edit.add_argument("--runtime", choices=runtime_names(), help="换绑执行体（换引擎不换大脑）")
    p_edit.add_argument(
        "--memory", action=argparse.BooleanOptionalAction, default=None, help="开/关长期记忆"
    )


def run_soul(args: argparse.Namespace, store: SoulStore) -> None:
    cmd = args.soul_command
    if cmd == "list":
        names = store.list_names()
        print("\n".join(names) if names else "暂无伙伴（vibegoing soul create <名字> 创建）")
    elif cmd == "show":
        print_soul(store.load(args.name))
    elif cmd == "create":
        _soul_create(args, store)
    elif cmd == "edit":
        _soul_edit(args, store)


def _soul_create(args: argparse.Namespace, store: SoulStore) -> None:
    if store.exists(args.name):
        print(f"伙伴 {args.name} 已存在：{store.path_for(args.name)}")
        return
    persona = args.persona
    principles = parse_tags(args.principles)
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
        capabilities=parse_tags(args.capabilities),
        runtime=getattr(args, "runtime", "llm") or "llm",
    )
    path = store.save(soul)
    print(f"已创建 {soul.emoji} {soul.name} → {path}")
    print_soul(soul)


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
        updates["principles"] = parse_tags(args.principles)
    if getattr(args, "capabilities", None) is not None:
        updates["capabilities"] = parse_tags(args.capabilities)
    if getattr(args, "runtime", None) is not None:
        updates["runtime"] = args.runtime
    if args.memory is not None:
        updates["memory_enabled"] = args.memory
    if not updates:
        print("未指定任何修改项（--emoji/--persona/--model/--principles/--memory）")
        return
    soul = soul.model_copy(update=updates)
    store.save(soul)
    print(f"已更新 {soul.name}：{', '.join(updates)}")
    print_soul(soul)


def _ai_persona(description: str, model: str) -> tuple[str, list[str]]:
    """用 LLM 依一句话描述生成人设与原则（VG-102 --ai）。"""
    from ..llm_utils import default_llm

    llm = default_llm(model)
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
