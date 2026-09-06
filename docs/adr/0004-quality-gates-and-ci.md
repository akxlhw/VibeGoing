# ADR 0004：质量门禁与 CI 基线

- 状态：已采纳（2026-09-06）
- 关联：PROCESS.md §5

## 背景

单人 + AI 的开发模式缺少人工评审环节，缺陷容易直接进入 main。需要机器可执行的工程纪律兜底。

## 决策

四道门禁本地与 CI 同口径，全部通过才允许合入：

| 门禁 | 工具 | 口径 |
|---|---|---|
| 静态检查 | ruff | E/W/F/I/UP/B/C4/SIM/RUF；豁免 RUF001-003（中文全角标点误报） |
| 格式化 | black | line-length 100 |
| 类型检查 | mypy | 产品代码（vibegoing/）全覆盖，测试目录暂不纳入 |
| 单元测试 | pytest | 全绿；行为测试优先 |

CI 用 GitHub Actions：push(main) 与 PR 触发，Python 3.12 + uv。

## 理由

- ruff+black+mypy 组合是 Python 社区当前的性价比最优解；mypy 已实际抓出存量代码的类型问题（memory 字段撞名）
- 行为测试而非实现测试，保证重构安全（PROCESS.md §7）
- 门禁在 pyproject.toml 单点配置，本地 `uv run` 与 CI 完全一致

## 后果与约束

- 新增依赖须同步 dev 组并保持 CI 绿
- 覆盖率门禁（VG-004）暂未启用，接入后目标为核心模块 ≥ 80%
