# VibeGoing 项目规划书

| | |
|---|---|
| 版本 | v1.0（2026-09-06） |
| 状态 | M0 已完成，M1 待启动 |
| 对标产品 | intovibe（引途心流，intovibe.ai） |
| 仓库 | github.com/akxlhw/VibeGoing（私有） |

---

## 1. 项目定位

**一句话定位**：本地优先的 AI 伙伴工作台——把 LLM 与 Coding Agent 变成有持久身份（Soul）、长期记忆、可协作的常驻队友，通过飞书融入真实工作流。

**底层策略**：CrewAI 仅作为依赖使用（MIT 协议，不改框架源码）；所有产品代码在本仓库独立演进，必要时以 fork 分支 + `tool.uv.sources` 指向补丁。

**目标用户**：

1. 已在用多个模型 / Coding Agent 的开发者和小团队
2. 以飞书为主要协作平台、希望 AI 在真实业务流程里交付的团队
3. 重视数据隐私、要求工作内容不出本机的用户

**与 intovibe 的差异化**：

| 维度 | intovibe | VibeGoing |
|---|---|---|
| 平台 | 仅 Mac | Windows 优先，跨平台（Python + Tauri） |
| 生态 | 飞书，企微/钉钉/Slack 规划中 | 飞书优先，中文模型生态（DeepSeek/GLM/Kimi）一等公民 |
| 形态 | 闭源商业产品 | 可自托管、可审计（是否开源见 §8 开放问题） |
| 底座 | 自研编排 | CrewAI 开源框架，享受其迭代与社区 |

---

## 2. 对标分析：intovibe 特性 → VibeGoing 方案

| # | intovibe 特性 | VibeGoing 方案 | 里程碑 | 状态 |
|---|---|---|---|---|
| 1 | 换引擎不换大脑（Runtime 可换，Soul 持久） | Soul 与 model/runtime 绑定分离，JSON 持久化 | M1 | ✅ 部分完成（模型级），M4 完成 Runtime 级 |
| 2 | Soul 长期人设（可编辑、结构化） | Soul 模型 + CLI 管理命令 + AI 辅助生成 | M1 | ✅ 已完成存储，命令待补 |
| 3 | 长期记忆（跨会话延续） | CrewAI 统一 Memory（LanceDB 本地），每轮召回/沉淀 | M0 | ✅ 已跑通，质量调优在 M1 |
| 4 | BYO Plan / BYO Key | LiteLLM 全 provider + .env 配置 | M0 | ✅ 已完成 |
| 5 | 一对一深度脑暴 | 会话型 Flow REPL / 飞书私聊 | M0/M2 | 终端 ✅，飞书在 M2 |
| 6 | 群内 @ 派活 | 飞书群聊 @ 解析 → 伙伴路由 | M2 | ⬜ |
| 7 | 多角色协同（CEO/CTO/COO） | hierarchical Crew + 角色绑定伙伴 | M3 | ⬜ |
| 8 | 多 Agent 交叉复核 | 产出 Agent + 复核 Agent 的 Crew 任务链 | M3 | ⬜ |
| 9 | AI 间接力交接 | 伙伴间上下文交接（A2A / 内部协议） | M3 | ⬜ |
| 10 | 按能力分派任务 | 任务路由：能力标签匹配伙伴 | M3 | ⬜ |
| 11 | CLI Agent 作为执行体（Claude Code/Codex…） | Runtime 抽象层 + headless CLI 适配器 | M4 | ⬜（**核心差异化，最大工程量**） |
| 12 | 飞书原生能力（文档/表格/项目） | 飞书开放 API 写回交付物 | M5 | ⬜ |
| 13 | 本地优先隐私（内容不经中央服务器） | 全数据本地（.vibe/），遥测关闭 | M0 | ✅ 已完成 |
| 14 | 桌面应用 + 移动端协作 | Tauri + Python sidecar 桌面壳；移动端经飞书 | M5 | ⬜ |

**明确不做（YAGNI）**：独立移动 App（飞书即是移动端）、Soul 生成向导 GUI（M1 用 CLI + AI 生成代替，GUI 到 M5 再评估）、多租户 SaaS（远期开放问题）。

---

## 3. 总体架构

```
┌─ 接入层 ─────────────────────────────────────────────┐
│  终端 REPL（现有） │ 飞书网关（M2：长连接 WS） │ Web UI（M5） │
└──────────────┬───────────────────────────────────────┘
               ▼
┌─ 伙伴层 ─────────────────────────────────────────────┐
│  TeammateFlow（CrewAI 会话型 Flow）                   │
│   ├── Soul（身份：人设/原则/绑定，JSON 持久化）        │
│   ├── Memory（统一记忆：recall → prompt，remember）    │
│   └── Runtime 绑定 ──┬─ LLM Runtime（LiteLLM，BYO Key）│
│                      └─ CLI Runtime（M4：headless 子进程）│
└──────────────┬───────────────────────────────────────┘
               ▼
┌─ 协作层（M3）─────────────────────────────────────────┐
│  Crew（hierarchical 派活 / 交叉复核）· 交接协议        │
└──────────────┬───────────────────────────────────────┘
               ▼
┌─ 交付与数据层 ────────────────────────────────────────┐
│  飞书文档/表格写回（M5）· SQLite 会话/任务台账 · LanceDB │
│  全部落在 VIBE_HOME（默认 ./.vibe），不出本机            │
└───────────────────────────────────────────────────────┘
```

**技术栈**：Python 3.10–3.13 · CrewAI ≥1.15（conversational Flow / Memory / Crew / A2A）· LiteLLM · LanceDB · SQLite · lark-oapi（飞书）· Tauri（M5）

**代码结构规划**（随里程碑生长）：

```
vibegoing/
├── soul.py / teammate.py     # M0 已有
├── session.py                # M1：会话持久化与恢复
├── memory_admin.py           # M1：记忆查看/遗忘
├── gateway/feishu.py         # M2：飞书长连接网关
├── collab/                   # M3：复核 Crew、派活、交接
├── runtimes/                 # M4：base.py + llm.py + claude_code.py + codex.py …
└── delivery/feishu_docs.py   # M5：交付物写回
```

---

## 4. 里程碑路线图

> 预估按一名熟悉 Python 的开发者全职计（人日），含测试与文档。

### M0 — 产品内核验证 ✅ 已完成（2026-09-06）

- Soul 存储（JSON）、TeammateFlow（会话 + 记忆召回/沉淀）、终端 REPL、BYO Key
- 冒烟测试 4 例（无 API Key 可跑）；依赖在 Windows 验证通过

### M1 — 单伙伴体验闭环（预估 3–5 人日）

**目标**：一个伙伴值得天天用——重启不丢上下文，Soul 和记忆可管理，回复可流式。

| 项 | 内容 |
|---|---|
| 会话持久化 | `@persist` + SQLite：`vibegoing --resume [id]` 跨进程恢复对话 |
| Soul 管理 | `vibegoing soul create/edit/show/list`；`--ai` 参数用 LLM 生成 persona 草稿 |
| 记忆管理 | `vibegoing memory list/forget/show`；召回噪声调优（阈值、scope 收紧） |
| 流式输出 | `stream_turn()` 接入 REPL（逐字打印） |
| 模型热切换 | `vibegoing --model <provider/model>` 临时换引擎，验证人设与记忆不变 |

**验收标准**：
1. 对话中途 Ctrl+C，`--resume` 后伙伴记得之前内容（会话与记忆双通道）
2. 用 openai→deepseek 两次对话同一伙伴，人设语气一致、记忆可召回
3. `memory list` 能看到沉淀记录，`forget` 后不再召回

### M2 — 飞书接入（预估 5–8 人日）

**目标**：产品从"终端玩具"变成"团队工具"——在飞书里 @ 你的伙伴干活。

| 项 | 内容 |
|---|---|
| 飞书应用骨架 | 自建企业应用，长连接（WebSocket）收消息，凭证存本地 |
| 私聊 | 用户 ↔ 伙伴 1:1 绑定（飞书 user_id → soul name），多轮上下文 |
| 群聊 @ 派活 | 群消息 @机器人 + @伙伴名 解析路由；未指名时按能力标签默认伙伴 |
| 回复体验 | 文本卡片回复；长任务先回"收到"再异步交付（任务台账） |
| 并发与限流 | 每会话串行、多会话并行；飞书 API 限速处理 |

**验收标准**：飞书私聊和群 @ 各完成一段 5 轮以上多轮对话；两条会话并发不串上下文；断网重连后恢复。

### M3 — 多伙伴协作（预估 5–8 人日）

**目标**：intovibe 的招牌体验——伙伴们互相配合、互相检查。

| 项 | 内容 |
|---|---|
| 交叉复核 | 一位伙伴产出 → 另一位（不同模型）复核 → 汇总结论的 Crew 任务链 |
| 层级派活 | hierarchical 流程：管理者 Agent 拆解并分派给绑定的伙伴 |
| 交接协议 | 伙伴 A 的产出与上下文打包交给伙伴 B 继续（先做内部协议，A2A 视成本） |
| 能力路由 | Soul 增加能力标签；群内未指名时自动匹配 |

**验收标准**：群内一条消息"调研 X 并写摘要"，自动完成 调研（伙伴A）→ 复核（伙伴B）→ 交付，全程 @ 发起人可见阶段进展。

### M4 — CLI Runtime 适配（预估 8–12 人日）★ 核心差异化

**目标**：intovibe 最难复刻也最值钱的能力——把 Claude Code / Codex 等 Coding Agent 变成伙伴的"手"。

| 项 | 内容 |
|---|---|
| Runtime 抽象 | `Runtime` 接口：submit(task) / stream(events) / cancel / health；LLM 与 CLI 同接口 |
| 首个适配器 | Claude Code headless（`claude -p --output-format stream-json`） |
| 第二适配器 | Codex（`codex exec`），验证抽象不复用反人类 |
| 任务台账 | SQLite：任务状态机（pending/running/done/failed）、超时、重试 |
| 权限门控 | 工作目录白名单、危险命令确认（先本地确认，M5 升级到飞书卡片审批） |

**验收标准**：伙伴绑定 Claude Code Runtime 完成一个真实编码任务（改一个 bug），全过程流式回传；换绑 Codex 后同一 Soul 继续指挥，任务台账完整。

### M5 — 交付与桌面化（预估 8–12 人日）

**目标**：像 intovibe 一样"装上就能用"，交付物落进飞书。

| 项 | 内容 |
|---|---|
| 飞书交付 | 伙伴产出写入飞书文档/多维表格（文档链接回聊天） |
| 桌面应用 | Tauri 壳 + Python sidecar daemon；安装包（Windows 优先，macOS/Linux 跟进） |
| 体验完善 | Soul 向导 GUI（五步：形象/名字/人设/Soul/Runtime）、自动更新、托盘常驻 |

**验收标准**：新机器安装 → 登录飞书 → 5 分钟内完成首位伙伴创建并派活。

### 远期（探索，不承诺）

多用户与权限（团队版）、企微/钉钉网关、Skills 市场、开源策略落地。

---

## 5. 关键技术设计

### 5.1 会话与持久化（M1）

每轮 `handle_turn` 已是独立 Flow 执行，配 `@persist(SQLiteFlowPersistence)` 后按 `session_id` 快照恢复。注意官方文档建议：**persist 挂在单个终止步骤而非整个类**，避免恢复到中间快照。记忆与会话双通道：会话恢复管"短期上下文"，Memory 管"长期沉淀"，两者职责不重叠。

### 5.2 Soul 与记忆模型

- Soul = 身份（persona/principles）+ 绑定（model/runtime）+ 开关（memory_enabled）。身份与绑定分离是"换引擎不换大脑"的实现基础。
- 记忆按 scope 隔离：`vibegoing/teammates/<name>`；后续协作记忆放 `vibegoing/teams/<crew>`。
- **已知约束**：统一 Memory 默认用 OpenAI embedding。全本地化方案（ollama embedding / BGE 本地模型）列为 M1 的可选任务，保证"拔掉 OpenAI Key 也能完整本地跑"。

### 5.3 Runtime 抽象（M4 的地基）

```python
class Runtime(Protocol):
    def submit(self, task: TaskSpec, *, on_event: Callable[[RuntimeEvent], None]) -> TaskHandle: ...
    def cancel(self, handle: TaskHandle) -> None: ...
    def health(self) -> RuntimeHealth: ...
```

- LLM Runtime 现有实现收敛到该接口；CLI Runtime 以子进程 + JSON 流事件实现同一接口
- 上层（TeammateFlow / 飞书网关）只面对 Runtime，不感知差异——这是"换引擎"的架构保证
- 每个适配器必须带版本契约测试（各家 CLI 协议随版本漂移）

### 5.4 安全与隐私红线

1. 工作内容（消息、记忆、任务、产出）只存 `VIBE_HOME`，进程不经任何第三方服务器（飞书消息本身除外）
2. `OTEL_SDK_DISABLED=true` 为默认配置（.env.example 已写入）
3. CLI Runtime 执行任意命令的风险必须由权限门控兜底：目录白名单 + 危险操作确认，绝不静默执行
4. 飞书凭证、API Key 只存本地 .env / .vibe/credentials，永不入库入 git

---

## 6. 风险与应对

| 风险 | 等级 | 应对 |
|---|---|---|
| CrewAI 会话型 Flow API 演进较快（刚从 experimental 转正） | 高 | 锁定 minor 版本；所有 CrewAI 调用收拢在 teammate.py/gateway 的薄封装层内，升级只改一处 |
| 各家 CLI headless 协议漂移 | 高 | 适配器隔离 + 版本契约测试矩阵；跟不上时降级提示用户锁版本 |
| 飞书开放平台审核/权限流程拖慢 M2 | 中 | 用企业自建应用先行（无需上架审核）；商店应用放远期 |
| 记忆召回噪声大影响体验 | 中 | M1 专项调优（阈值、scope、importance 权重）；提供 memory 管理命令让人工修剪 |
| CLI Agent 在本机执行代码的安全面 | 高 | M4 权限门控为验收前提，不是附加项 |
| 单人开发带宽 | 中 | 里程碑串行、验收标准明确；M1–M3 不依赖 CLI 适配，可独立交付价值 |
| lancedb/chromadb Windows 兼容 | 低 | M0 已实测通过；uv.lock 锁定 |

---

## 7. 节奏汇总

| 里程碑 | 内容 | 预估 | 累计 |
|---|---|---|---|
| M0 ✅ | 内核验证 | 已完成 | — |
| M1 | 单伙伴闭环 | 3–5 人日 | ~1 周 |
| M2 | 飞书接入 | 5–8 人日 | ~2.5 周 |
| M3 | 多伙伴协作 | 5–8 人日 | ~4 周 |
| M4 | CLI Runtime | 8–12 人日 | ~6.5 周 |
| M5 | 交付与桌面化 | 8–12 人日 | ~9 周 |

单人全职约 2 个月出头到 M5；兼职（晚上/周末）约 4–5 个月。M1–M2 完成即有日常可用产品，M4 完成即具备与 intovibe 正面对话的核心能力。

---

## 8. 开放问题（需要产品决策）

1. **开源时机**：M2 后产品形态清晰时开源核心（桌面壳闭源）？还是保持私有？（影响 M4 是否接受社区适配器贡献）
2. **首个 CLI Runtime 选型**：默认 Claude Code（协议最成熟）还是 Codex？建议 Claude Code。
3. **桌面壳形态**：Tauri（轻、跨平台好）vs Electron（生态熟）；倾向 Tauri + Python sidecar。
4. **记忆全本地化**：是否在 M1 就引入本地 embedding（多 1–2 人日），换取"无 OpenAI Key 全本地可用"的完整故事？
