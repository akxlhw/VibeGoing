# VibeGoing

基于 [CrewAI](https://github.com/crewAIInc/crewAI) 的**本地优先 AI 伙伴工作台**：把你的 LLM 变成有持久身份（Soul）和长期记忆的常驻伙伴。项目目标是逐步实现 intovibe 式的核心体验——换引擎不换大脑、长期记忆、多伙伴协作——并以独立应用的方式构建（CrewAI 仅作为依赖，不改框架源码）。

> 📋 完整的里程碑路线图、验收标准与风险分析见 [PLAN.md](PLAN.md)。

## 当前能力（v0.1）

- **Soul 持久身份**：每位伙伴的人设、工作原则、模型绑定存为本地 JSON（`.vibe/souls/`），可手工编辑
- **长期记忆**：基于 CrewAI 统一 Memory（LanceDB 本地存储），每轮对话前召回相关记忆、回复后自动沉淀
- **常驻对话**：基于 CrewAI 会话型 Flow，内置终端 REPL
- **BYO Key**：任意 LiteLLM 支持的模型（OpenAI / Anthropic / DeepSeek / Ollama 本地模型等）

## 快速开始

```bash
# 需要 Python 3.10–3.13 和 uv
uv sync

cp .env.example .env   # 填入你的 API Key 和模型选择

uv run vibegoing       # 与默认伙伴 Ava 对话
```

常用命令：

```bash
uv run vibegoing --soul bob   # 换一位伙伴（不存在则按模板创建）
uv run vibegoing --list       # 列出所有伙伴
uv run pytest                 # 冒烟测试（无需 API Key）
```

## 配置

见 `.env.example`：`VIBE_LLM`（模型）、`VIBE_MEMORY`（记忆开关）、`VIBE_HOME`（数据目录）。所有数据（Soul、向量记忆库）都在本地 `VIBE_HOME` 下，不出本机。

## 架构

```
用户（终端 REPL，后续：飞书网关）
   └── TeammateFlow（CrewAI conversational Flow）
         ├── Soul（人设 + 原则 + 模型绑定，JSON 持久化）
         ├── LLM（BYO Key，LiteLLM 格式换引擎）
         └── Memory（统一记忆：recall → 注入 prompt；remember → 沉淀）
```

## 路线图

- [ ] M1 单伙伴闭环：会话跨进程恢复、Soul/记忆管理命令、流式输出
- [ ] M2 多伙伴协作：交叉复核 Crew、层级式派活、能力路由、交接
- [ ] M3 CLI Runtime 适配器：把 Claude Code / Codex 等 headless CLI 作为执行体挂到伙伴上
- [ ] M4 桌面化：Tauri + Python sidecar、Soul 创建向导 GUI
- [ ] M5 飞书接入与交付：长连接网关、群内 @ 派活、文档/表格写回（最后一个里程碑）

## 开发流程与文档

本项目以敏捷方式运作（详见 [开发流程与工程规范](docs/agile/PROCESS.md)）：故事化管理（[BACKLOG](docs/agile/BACKLOG.md)）、周冲刺（[冲刺档案](docs/agile/sprints/)）、四道质量门禁（ruff / black / mypy / pytest，CI 强制）、架构决策记录（[ADR](docs/adr/)）、[变更日志](CHANGELOG.md)。所有变更经特性分支进入 `main`。

## License

MIT（依赖的 CrewAI 同为 MIT）
