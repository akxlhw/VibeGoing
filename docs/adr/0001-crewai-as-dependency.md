# ADR 0001：CrewAI 作为依赖使用，而非 Fork

- 状态：已采纳（2026-09-06）
- 关联：PLAN.md §1

## 背景

产品需要多 Agent 编排、会话循环与长期记忆三大能力。可选路径：A. 独立仓库以 PyPI 依赖引入 CrewAI；B. Fork CrewAI 源码在其上开发；C. 完全自研。

## 决策

采用路径 A：`crewai>=1.15.20,<2` 作为普通依赖；产品代码独立演进。

## 理由

- 产品是应用程序，CrewAI 是框架，两层天然分离；公开 API（conversational Flow、Memory、Crew、A2A）已覆盖需求
- 免去同步上游 fork 的持续成本；升级只改版本号
- 产品仓库保持私有（GitHub 公开仓库的 fork 无法转私有）
- MIT 协议允许闭源商用，仅需保留版权声明

## 后果与约束

- CrewAI 触点以 [docs/dev/CREWAI_TOUCHPOINTS.md](../dev/CREWAI_TOUCHPOINTS.md) 为权威清单，升级框架时逐项核对；新增触点须登记
- 若未来必须改框架内部：fork 出 `product-patches` 分支，产品以 `tool.uv.sources` 指向，并尽量将补丁 PR 回上游（路线 C 混合方案）
- CrewAI API 变动的风险由"薄封装"缓解：所有框架调用收拢在 teammate.py 等少数模块（见 PROCESS.md §7）
