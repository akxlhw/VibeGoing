"""交接协议（VG-203）：伙伴间任务与上下文的标准化传递。

协议 v1 约定：
- 一次交接 = 任务描述 + 委托方/接手方 + 背景说明 + 已有产出清单 + 期望产出
- 报文可 JSON 序列化（为跨进程/跨 Runtime 传输预留），亦可用 to_prompt()
  渲染为接手方的直接提示词
- 委托方与接手方必须是不同伙伴（同侩交接无意义）
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class HandoffPacket(BaseModel):
    """伙伴 → 伙伴的一次任务交接报文。"""

    task: str
    from_agent: str
    to_agent: str
    context: str = ""
    prior_outputs: list[dict[str, str]] = Field(
        default_factory=list,
        description="上游产出清单，[{'source': 来源伙伴/阶段, 'output': 产出}]",
    )
    expectations: str = ""

    @model_validator(mode="after")
    def _agents_differ(self) -> HandoffPacket:
        if self.from_agent == self.to_agent:
            raise ValueError("交接双方必须是不同的伙伴")
        return self

    def to_prompt(self) -> str:
        """渲染为接手方的提示词：包含全部交接上下文。"""
        sections = [f"# 任务交接\n任务：{self.task}"]
        if self.context:
            sections.append(f"背景：{self.context}")
        if self.prior_outputs:
            prior = "\n".join(f"- [{p['source']}] {p['output']}" for p in self.prior_outputs)
            sections.append(f"已有产出：\n{prior}")
        if self.expectations:
            sections.append(f"期望产出：{self.expectations}")
        sections.append(
            f"以上任务由 {self.from_agent} 移交给你（{self.to_agent}），"
            "请基于已有产出继续，不要重复已完成的工作。"
        )
        return "\n\n".join(sections)
