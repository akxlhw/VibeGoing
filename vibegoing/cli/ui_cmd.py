"""ui 命令（M4 桌面化）：本地服务 + 桌面窗口（WebView2）优先、浏览器保底。

只监听 127.0.0.1（本地优先红线）。窗口依赖 pywebview（Windows 走 WebView2）；
未安装或初始化失败时自动回退为默认浏览器。
"""

from __future__ import annotations

import argparse
import threading
import time
import webbrowser

from ..server.app import create_app
from .common import home_arg


def add_ui_arguments(sub: argparse._SubParsersAction) -> None:
    ui = sub.add_parser("ui", help="启动图形界面（本地服务 + 桌面窗口/浏览器）")
    ui.add_argument("--port", type=int, default=8791, help="本地端口（默认 8791，仅 127.0.0.1）")
    ui.add_argument("--no-window", action="store_true", help="不开桌面窗口，用默认浏览器打开")


def run_ui(args: argparse.Namespace) -> None:
    import uvicorn

    home = home_arg(args.home)
    app = create_app(home)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning")
    )
    url = f"http://127.0.0.1:{args.port}"
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):  # 等服务就绪
        if server.started:
            break
        time.sleep(0.1)

    if args.no_window:
        print(f"🌿 VibeGoing 界面已就绪：{url}（Ctrl+C 退出）")
        webbrowser.open(url)
        thread.join()
        return

    try:  # 桌面窗口优先（Windows = WebView2）  # pragma: no cover - 窗口路径不进 CI
        import webview

        print(f"🌿 VibeGoing 桌面窗口已打开（服务 {url}，关闭窗口即退出）")
        webview.create_window("VibeGoing · 本地 AI 伙伴工作台", url, width=1240, height=840)
        webview.start()
        server.should_exit = True
    except Exception as exc:  # pragma: no cover - 回退路径不进 CI
        print(f"（桌面窗口不可用：{exc}，已回退浏览器）🌿 {url}")
        webbrowser.open(url)
        thread.join()
