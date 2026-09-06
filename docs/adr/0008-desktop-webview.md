# ADR 0008：桌面化实现选型——本地 Web UI + pywebview 窗口（Tauri 排除）

- 状态：已采纳（2026-09-07）
- 关联：PLAN.md §4 M4、BACKLOG VG-401~404、ADR 0001/0007

## 背景

M4 原计划"Tauri 壳 + Python sidecar + Windows 安装包 + 托盘常驻"。PO 目标强调
"复用 intovibe 的 UI 风格"完成 v0.5.0。开发机实测（2026-09-07）：

- `cargo`/`rustc` **不存在** → Tauri 构建链不可用（引入 Rust 工具链 + 首次全量编译
  在当前环境风险与耗时不可接受）
- WebView2 运行时**已装**（152.x 双版本）→ pywebview 原生窗口可用
- Electron 方案需 ~100MB 运行时下载（网络不稳定）且内存占用高，排除
- PyInstaller 打包全量依赖（crewai/chromadb/lancedb 原生库）体积 ~1GB 级、
  hidden-imports 风险高，安装包目标推迟

## 决策

1. **架构**：FastAPI 本地服务（**仅监听 127.0.0.1**，本地优先红线）+ 纯静态前端
   （无构建链）+ `vibegoing ui` 入口：pywebview 桌面窗口优先、`--no-window` 浏览器保底
2. **UI 风格**：复刻 intovibe 视觉语言（站面实测提取）——暖白底/墨色文字/鼠尾草绿
   点缀/圆形头像/编号节标（01-06 + 英文前缀）/分段控件/胶囊箭头 CTA/
   五步向导（01形象 02名字 03人设 04Soul 05Runtime + "Soul 一键生成 ✨"）
3. **M4 验收修订**（原验收"新机器安装→5 分钟图形界面完成创建+派活"）：
   - ✅ 保留：图形界面完成首位伙伴创建并派活（向导 5 步 + 聊天，全程不碰终端配置）
   - ✅ 安装路径修订为：`uv tool install vibegoing && vibegoing ui`（一条命令即用）
   - ⏭ 推迟（VG-405，登记待办）：原生安装包（exe/installer）、系统托盘常驻、
     自动更新通道（v0.5.0 设置页提供版本与升级指引作为通道 v1）

## 后果与约束

- UI 逻辑无浏览器端测试链（无构建链的取舍）；API 层 TestClient 全覆盖，
  界面验收依赖 PO 演示（评审记录附指引）
- 服务仅本机可访问，无鉴权（localhost 边界即安全边界；若未来开放局域网需先加鉴权，红线）
- 流式输出：服务端暂为整段返回，前端打字机呈现；SSE 升级列后续优化
