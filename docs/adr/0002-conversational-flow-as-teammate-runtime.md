# ADR 0002：以 CrewAI 会话型 Flow 作为伙伴的运行时基座

- 状态：已采纳（2026-09-06）
- 关联：PLAN.md §5、ADR 0001

## 背景

伙伴（Teammate）需要常驻多轮对话、逐轮处理消息、维护会话历史。CrewAI 的 Crew 是面向"任务批处理"的抽象，Agent 是面向"LLM+工具循环"的抽象，均非长会话模型。

## 决策

伙伴以 `Flow[ConversationState]` + `@ConversationConfig` 实现：每条用户消息经 `handle_turn(message, session_id=...)` 触发一轮图执行；覆盖内置 `converse_turn()` 注入 Soul 身份与召回的记忆。多 Agent 协作（M2）时才组 Crew。

## 理由

- 会话型 Flow 与 IM/REPL 的"每消息一轮"模型天然同构，事件驱动也匹配后续网关形态
- 官方提供消息历史、意图路由、`chat()` REPL、`@persist` 快照，均为现成能力
- Crew 留给真正需要多角色协同的场景，避免把伙伴硬套进任务批处理抽象

## 后果与约束

- `converse_turn` 的覆盖实现是我们的核心定制点，框架升级时优先回归测试此处
- **已知陷阱**：`RuntimeFlow` 基类已声明 `memory` 字段（`Memory | MemoryScope | MemorySlice` 联合类型）。伙伴自有的记忆后端必须命名为 `memory_backend`，直接用 `self.memory` 会与框架字段冲突（mypy 可检出）
- 该模块（teammate.py）是 ADR 0001 所述"薄封装"的主要落点
