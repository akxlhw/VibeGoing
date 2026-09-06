"""终端入口：`vibegoing` 或 `python -m vibegoing` 启动与伙伴的对话。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

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
    args = parser.parse_args()

    home = Path(args.home or os.environ.get("VIBE_HOME", "./.vibe")).expanduser().resolve()
    store = SoulStore(home / "souls")

    if args.list:
        for name in store.list_names():
            print(name)
        return

    soul = store.load_or_create(args.soul, template=default_soul())
    if env_model := os.environ.get("VIBE_LLM"):
        soul = soul.model_copy(update={"model": env_model})

    print(f"{soul.emoji} {soul.name} 已就绪（模型：{soul.model}，记忆：{'开' if soul.memory_enabled else '关'}）")
    print("输入 exit / quit 结束对话。\n")

    flow = TeammateFlow(soul=soul, vibe_home=home)
    try:
        flow.chat()
    finally:
        flow.finalize_session_traces()
        flow.close()


if __name__ == "__main__":
    main()
