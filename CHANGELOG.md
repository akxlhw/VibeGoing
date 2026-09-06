# 变更日志（Changelog）

本文件记录用户可感知的变化。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。日期为发布日。

## [Unreleased]

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
