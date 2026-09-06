# ADR 0007：Runtime 统一抽象与 CLI 适配器设计

- 状态：已采纳（2026-09-06）
- 关联：PLAN.md §5.3、BACKLOG VG-301~305、ADR 0002/0006

## 背景

M3 要把 Claude Code / Codex 等 headless CLI 变成伙伴的"手"。LLM 调用（既有路径）
与 CLI 子进程执行必须对上层（TeammateFlow、协作管线、未来的飞书网关）不可区分，
"换引擎不换大脑"才有架构保证。PLAN.md §5.3 预定义了协议草案。

## 决策

1. **协议**：`Runtime.submit(task, on_event) -> TaskHandle`、`cancel(handle)`、
   `health()`；`TaskSpec`（instruction/workdir/timeout_s）、`RuntimeEvent`
   （stdout/status/done/error）、`TaskHandle.wait()/result/events`
2. **并发模型**：submit 后台线程执行，事件实时回调；wait 阻塞取产出；
   CLI 适配器超时/取消通过 terminate 进程实现
3. **可测试性**：CLI 适配器的进程启动经 `spawn` 参数注入（生产用
   subprocess.Popen，测试用假进程对象）——与 M2 替身 LLM 同一思路，
   无真实 CLI 也能全链路行为测试；真实 runner 路径用无害子进程
   （python -c）覆盖
4. **红线前置**：所有 CLI 适配器 submit 前必须过 `PermissionGuard`
   （ADR 同批 VG-305），拒绝即抛 `PermissionDenied`，绝不启动进程
5. **LLM 收敛**：`LLMRuntime` 包装既有 llm.call 为参考实现；
   TeammateFlow 按 `Soul.runtime` 字段经注册表取执行体

## 后果与约束

- 超时判定在"行间"进行（逐行读取间检查墙钟）：完全不输出的僵死进程
  在收到首行/EOF 前不会被 timeout 杀掉——已知限制，记入发布评审
- 各家 CLI 协议随版本漂移：适配器解析逻辑集中在 `_parse_line` 单方法，
  为 VG-306（版本契约测试矩阵）预留最小改动面
- Codex 适配器使用纯文本输出（codex exec 无稳定 JSON 流契约），
  Claude Code 适配器解析 stream-json
