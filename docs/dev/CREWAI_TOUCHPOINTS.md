# CrewAI 触点清单（升级检查表）

> ADR-0001 要求"CrewAI 调用收拢在少数模块"。本清单是权威触点列表：
> **升级 CrewAI 版本时逐项核对**，新增触点必须同步登记于此（PROCESS.md §5 文档门禁）。

| # | 模块 | 触点性质 | 升级时检查什么 |
|---|------|---------|---------------|
| 1 | `vibegoing/teammate.py` | **核心调用**：conversational Flow、`@persist`、`@ConversationConfig`、`converse_turn` 覆盖、统一 Memory 构造、`_conversation_streaming_enabled` 私有 API、`RuntimeFlow.memory` 字段避让 | 会话 API 签名、快照恢复行为、stream 帧 channel/type 契约、Memory 构造参数 |
| 2 | `vibegoing/llm_utils.py` | LLM 构造（`crewai.LLM`） | 构造参数与 provider 解析 |
| 3 | `vibegoing/runtimes/base.py` | 类型导入（`crewai.utilities.types.LLMMessage`） | 类型定义位置 |
| 4 | `vibegoing/collab/pipeline.py` | 类型导入（同上） | 同上 |

已知的框架私有 API 使用（版本升级高风险区）：

- `teammate.py`：`_conversation_streaming_enabled`（流式开关）、`_instance_persistence`
  标志置位（后挂载持久化后端）——来源 ADR-0002，升级时必须回归
  `test_session_restores_across_fresh_instances` 与流式相关测试
- `teammate.py`：实例属性命名 `memory_backend`，避让 `RuntimeFlow.memory` 字段（ADR-0002）

延迟导入约定（ADR-0007 补充，2026-09-06）：

- `teammate.py ↔ runtimes.{registry,base,executor}` 存在**函数内延迟互调**——这是
  有意设计（避免模块加载期的循环依赖），不是 bug，不要"修复"为顶层导入；
  新增跨层调用时优先：顶层导入单向依赖（cli → teammate/collab/runtimes → 共享层），
  只有确实双向时才允许延迟导入并在此登记
