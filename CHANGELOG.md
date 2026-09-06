# 变更日志（Changelog）

本文件记录用户可感知的变化。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。日期为发布日。

## [Unreleased]

## [0.5.0] - 2026-09-07

M4 桌面化：intovibe 风格图形界面（实现选型与验收修订见 ADR-0008）。

### Added
- **图形界面（VG-401）**：`vibegoing ui` 启动本地服务（仅 127.0.0.1）+ 桌面窗口（WebView2）优先、浏览器保底；intovibe 视觉语言（暖白/鼠尾草绿/圆形头像/编号节标/胶囊箭头 CTA）
- **五步创建向导（VG-402）**：01 形象（摇一摇）→ 02 名字 → 03 人设（**Soul 一键生成 ✨**）→ 04 Soul（原则/能力标签）→ 05 Runtime（六执行体单选，健康状态标注）
- **聊天界面**：伙伴切换、会话接续与历史恢复、打字机输出；**危险操作放行审批（VG-403）**——CLI 伙伴被门控拒绝时出现审批条，勾选放行后可重发
- **任务面板（VG-403）**：协作任务一键运行、状态轮询、阶段产物逐段查看
- **执行体/设置页**：六执行体健康检查；版本徽章与升级指引（VG-404 通道 v1）、隐私边界说明
- 服务端 API（TestClient 全覆盖 9 例）：souls CRUD、chat、会话历史、crew 后台执行（防双记录）、persona 草稿、危险标签
- 结构重构收编（2026-09-06 审计偿还）：cli 拆包、台账/LLM 工厂归位共享层、CrewAI 触点清单

### Deferred
- 原生安装包、系统托盘、SSE 流式（登记 VG-405，见 ADR-0008 推迟理由与工具链实测证据）

## [0.4.1] - 2026-09-06

国内 Coding Agent 适配（PO 指令插入版；版本策略例外已在 RELEASE_PLAN 记录）。

### Added
- **ZCode 适配器（VG-307）**：`zcode -p <指令>` 无头模式（智谱 Z.AI）；桌面内置 CLI 可经 `VIBE_ZCODE_BIN` 指向实际二进制
- **Kimi Code 适配器（VG-308）**：`kimi -p <指令> --auto` 无头全自主模式（月之暗面）；外层权限边界仍由 PermissionGuard 承担
- **DeepSeek Harness 适配器（VG-309）**：`dsh --profile headless <任务>`（打印最终答案退出，工作目录即工作区根）
- 通用：`VIBE_<执行体名>_BIN` 环境变量覆盖二进制路径（桌面内置 CLI 不在 PATH 的场景）；`runtime list/check` 与 `soul --runtime` 选项统一从注册表生成（现支持 6 个执行体：llm / claude-code / codex / zcode / kimi-code / deepseek-harness）

## [0.4.0] - 2026-09-06

M3 CLI Runtime（核心差异化）：把 Claude Code / Codex 变成伙伴的"手"。

### Added
- **Runtime 统一抽象（VG-301）**：LLM 与 CLI 执行体同接口（submit/cancel/health，事件流式回调）；设计决策见 ADR-0007
- **Claude Code 适配器（VG-302）**：`claude -p <指令> --output-format stream-json`，stream-json 解析、超时终止、取消、非零退出检查
- **Codex 适配器（VG-303）**：`codex exec <指令>`，复用同一进程基座；`soul edit <名字> --runtime codex` 换绑后 Soul 身份/记忆/会话不变（换引擎不换大脑）
- **权限门控（VG-305，红线）**：CLI 执行前强制检查——工作目录白名单（`VIBE_ALLOWED_DIRS`，默认仅当前目录）+ 九类危险指令模式审批（`rm -rf`/`sudo`/管道执行远程脚本/强推/删库等），无审批通道直接拒绝，绝不静默执行
- **重试与台账（VG-304）**：`run_with_retry` 瞬时故障（超时/非零退出）自动重试，每次尝试落任务台账（`crew status` 可查）；权限拒绝不消耗重试
- **伙伴绑定 Runtime**：`soul create/edit --runtime llm|claude-code|codex`；CLI 伙伴的对话轮次自动经执行体完成，输出逐字流式打印，产出/失败落台账；`vibegoing runtime list|check` 健康检查

### Security
- CLI 子进程一律参数直传不经 shell；执行前权限门控为硬性前置（拒绝即不启动进程）

## [0.3.0] - 2026-09-06

M2 多伙伴协作：伙伴们互相配合、互相检查。

### Added
- **交叉复核（VG-201）**：`vibegoing crew run "任务"` 一条命令完成 产出 → 复核 → 汇总交付，复核意见随交接上下文回流给产出方修订
- **层级派活（VG-202）**：`--mode hierarchy` 管理者拆解任务为带指派的阶段计划并依次执行，交接上下文跨阶段累积
- **交接协议（VG-203）**：伙伴间任务/上下文标准化传递（JSON 可序列化），详见 ADR-0006
- **能力路由（VG-204）**：Soul 新增 `capabilities` 能力标签（`soul create/edit --capabilities`），任务未指名时按标签匹配伙伴、点名优先
- **任务台账（VG-205）**：协作任务与各阶段产物落本地 SQLite；`crew status [ID]` 查看全过程（默认最近，ID 前缀），`crew list` 一览
- 开箱体验：复核伙伴不足时按模板自动创建（Bob 🔍）
- 覆盖率门禁（VG-004）：pytest-cov 阈值 80%（当前实际 90%），本地与 CI 同口径

### Changed
- M2 编排采用自研轻量管线而非 crewai.Crew（可测试性/伙伴身份一致性/YAGNI，见 ADR-0006）

## [0.2.0] - 2026-09-06

M1 单伙伴体验闭环：一个伙伴值得天天用。

### Added
- **会话跨进程恢复（VG-101）**：对话快照持久化到本地 SQLite；`--resume [SESSION_ID]` 恢复（不带参数取最近一次，支持 ID 唯一前缀），`--list-sessions` 查看历史会话
- **Soul 管理命令（VG-102）**：`vibegoing soul create/edit/show/list`；create 支持 `--ai` 用 LLM 按一句话描述生成人设
- **记忆管理命令（VG-103）**：`vibegoing memory list/show/forget`，支持 `--soul` 限定范围与 ID 前缀匹配
- **流式输出（VG-104）**：REPL 中 LLM 回复逐字打印，非流式运行时回退整段输出
- **模型热切换（VG-105）**：`--model PROVIDER/MODEL` 临时换引擎（优先级：CLI 参数 > `VIBE_LLM` > Soul 绑定），Soul 身份与记忆不变
- **召回质量调优（VG-106）**：相关度阈值过滤（默认 0.35，`VIBE_RECALL_MIN_SCORE` 可调）、同记录去重、单轮最多注入 3 条记忆

### Fixed
- CLI 子命令与根参数同名冲突导致的路径解析错误（`--home`）
- CI 失败：mypy 检查目标版本与 numpy 桩的 PEP 695 语法不兼容，目标版本升至 3.12

## [0.1.0] - 2026-09-06

### Added
- Soul 持久身份：人设/原则/模型绑定存为本地 JSON，换引擎不换大脑
- TeammateFlow 会话型伙伴：每轮召回长期记忆注入 system prompt，回复后自动沉淀（LanceDB 本地）
- 终端 REPL（`uv run vibegoing`），BYO Key 走 LiteLLM
- 冒烟测试 4 例（无需 API Key）
