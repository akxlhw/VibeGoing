"""终端入口：`vibegoing` 或 `python -m vibegoing` 启动与伙伴的对话。"""

from __future__ import annotations

from .cli import main

__all__ = ["main"]


if __name__ == "__main__":
    main()
