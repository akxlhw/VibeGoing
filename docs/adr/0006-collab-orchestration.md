# ADR 0006：多伙伴协作的编排实现——自研管线而非 crewai.Crew

- 状态：已采纳（2026-09-06）
- 关联：PLAN.md §4 M2、BACKLOG VG-201/202、ADR 0001/0002

## 背景

M2 需要交叉复核、层级派活、伙伴交接。BACKLOG 原始表述为"Crew 任务链 / hierarchical 流程"，
即直接使用 `crewai.Crew`（含 `Process.hierarchical`）。

## 决策

v0.3.0 的协作层（`vibegoing/collab/pipeline.py`）自研轻量编排：按阶段直接调用
各伙伴的 LLM（与 `TeammateFlow.converse_turn` 相同的 `llm.call` 模式），
阶段间用 `HandoffPacket`（ADR 同批引入）传递上下文，产物落 `TaskLedger`。
不使用 `crewai.Crew` / `Process.hierarchical`。

## 理由

1. **可测试性**：Crew 的执行路径深度依赖真实 LLM 行为，无法在无 API Key 的
   CI 中做行为测试；自研管线可用替身 LLM 全链路验证（项目 DoD 的硬性要求）
2. **伙伴身份一致性**：协作参与者必须是"Soul + 记忆"定义的伙伴，而非临时
   构造的 CrewAI `Agent`；自研管线能复用与 TeammateFlow 完全相同的身份注入
   与记忆召回/沉淀路径
3. **YAGNI**：M2 的协作形态是确定性的阶段流水线（产出→复核→汇总），不需要
   Crew 提供的自主委派、工具循环等能力

## 后果与约束

- "层级派活"（VG-202）实现为：管理者 LLM 先拆解任务为带指派的阶段计划
  （JSON），管线按计划执行——与 Crew hierarchical 的自治程度不同，这是有意的
- 当协作需要 Agent 间**自主**委派（如复核中发现需要追加调研并自行发起）时，
  重新评估引入 Crew/A2A，届时以新 ADR 记录
- BACKLOG 中"Crew 任务链"的表述按本 ADR 修正为"编排管线"，评审记录同步注明
