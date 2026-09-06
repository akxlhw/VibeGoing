"""终端入口：`vibegoing` 或 `python -m vibegoing` 启动与伙伴的对话。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from .session import SessionStore
from .soul import SoulStore, default_soul
from .teammate import TeammateFlow


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="vibegoing",
        description="与你的本地 AI 伙伴对话（基于 CrewAI 的会话型 Flow）",
    )
    parser.add_argument("--soul", default="ava", help="伙伴名字（默认 ava，不存在则按模板创建）")
    parser.add_argument("--home", default=None, help="数据目录（默认取 VIBE_HOME 或 ./.vibe）")
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
    args = parser.parse_args()

    home = Path(args.home or os.environ.get("VIBE_HOME", "./.vibe")).expanduser().resolve()
    store = SoulStore(home / "souls")
    session_store = SessionStore(home / "sessions.db")

    if args.list:
        for name in store.list_names():
            print(name)
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

    soul = store.load_or_create(args.soul, template=default_soul())
    if env_model := os.environ.get("VIBE_LLM"):
        soul = soul.model_copy(update={"model": env_model})

    # 解析会话：--resume 指定恢复，否则开新会话
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
        flow.chat(session_id=session_id)
    finally:
        flow.finalize_session_traces()
        flow.close()


if __name__ == "__main__":
    main()
