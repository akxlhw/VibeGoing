# 变更日志（Changelog）

本文件记录用户可感知的变化。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。日期为提交日。

## [Unreleased]

### Added
- 工程基线：ruff / black / mypy 质量门禁配置与 GitHub Actions CI（VG-001/002）
- 敏捷与工程文档体系：PROCESS（流程与 DoD）、BACKLOG（待办清单）、冲刺档案、ADR ×5（VG-001/002）

### Fixed
- 伙伴记忆记录中的回复者名字硬编码为"Ava"的问题——现使用伙伴实际名字
- 伙伴记忆后端属性与 CrewAI Flow 基类 `memory` 字段撞名的隐患——更名为 `memory_backend`

## [0.1.0] - 2026-09-06

### Added
- Soul 持久身份：人设/原则/模型绑定存为本地 JSON，换引擎不换大脑
- TeammateFlow 会话型伙伴：每轮召回长期记忆注入 system prompt，回复后自动沉淀（LanceDB 本地）
- 终端 REPL（`uv run vibegoing`），BYO Key 走 LiteLLM
- 冒烟测试 4 例（无需 API Key）
