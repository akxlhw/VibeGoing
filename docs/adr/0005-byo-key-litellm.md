# ADR 0005：模型接入统一走 LiteLLM（BYO Key）

- 状态：已采纳（2026-09-06）
- 关联：PLAN.md §1 差异化、ADR 0001

## 背景

产品承诺 BYO Key、中文模型生态一等公民（DeepSeek/GLM/Kimi）、支持本地模型。需要统一的模型接入层。

## 决策

模型标识统一使用 LiteLLM provider 字符串（如 `openai/gpt-4o`、`deepseek/deepseek-chat`、`ollama/llama3`），经 CrewAI 的 `LLM` 类（内部即 LiteLLM）调用；Soul 的 `model` 字段与 `VIBE_LLM` 环境变量均为该格式，密钥一律从环境/.env 读取。

## 理由

- 一套字符串格式覆盖全部主流 provider，换引擎 = 改一个字段，与"换引擎不换大脑"的产品主张一致
- 不自建模型抽象，避免与框架的 LLM 层重复

## 后果与约束

- 已知缺口：统一 Memory 默认用 OpenAI embedding——"无 OpenAI Key 全本地可用"需 VG-107（本地 embedding）补齐
- 密钥永不入库入 git（.gitignore 已排除 .env）；文档示例只出现占位符
