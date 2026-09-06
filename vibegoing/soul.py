"""Soul：伙伴的持久身份，与底层模型解耦。

Soul 是 intovibe 式的"心智"——人设、工作原则、记忆开关和模型绑定。
换引擎（model 字段）不影响 Soul 本身：人设与记忆跨模型延续。
每个 Soul 存为 VIBE_HOME/souls/<name>.json，可直接手工编辑。
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class Soul(BaseModel):
    """一位 AI 伙伴的完整身份定义。"""

    name: str
    emoji: str = "🤖"
    persona: str = ""
    principles: list[str] = Field(default_factory=list)
    # LiteLLM provider 字符串。换模型只改这里，人设与记忆不动。
    model: str = "openai/gpt-4o"
    memory_enabled: bool = True

    def identity_prompt(self) -> str:
        """渲染为注入 system prompt 的身份描述。"""
        parts: list[str] = []
        if self.persona:
            parts.append(f"# 你是谁\n{self.persona}")
        if self.principles:
            rules = "\n".join(f"- {p}" for p in self.principles)
            parts.append(f"# 工作原则\n{rules}")
        return "\n\n".join(parts)


class SoulStore:
    """以 JSON 文件形式管理 Soul 的本地存储。"""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, name: str) -> Path:
        return self.root / f"{name.lower()}.json"

    def exists(self, name: str) -> bool:
        return self.path_for(name).exists()

    def save(self, soul: Soul) -> Path:
        path = self.path_for(soul.name)
        path.write_text(soul.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, name: str) -> Soul:
        path = self.path_for(name)
        if not path.exists():
            raise FileNotFoundError(f"找不到 Soul：{path}（先用 vibegoing --soul {name} 创建）")
        return Soul.model_validate_json(path.read_text(encoding="utf-8"))

    def load_or_create(self, name: str, template: Soul | None = None) -> Soul:
        if self.exists(name):
            return self.load(name)
        soul = (template or default_soul()).model_copy(update={"name": name})
        self.save(soul)
        return soul

    def list_names(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.json"))


def default_soul() -> Soul:
    """首位伙伴的出厂模板。"""
    return Soul(
        name="ava",
        emoji="🎯",
        persona=(
            "你是 Ava，一位资深的产品工程师伙伴。你熟悉从需求拆解、技术选型 "
            "到落地交付的全流程，回答直接、务实、不堆砌套话。用户是团队里的 "
            "开发者，你可以默认对方具备工程背景。"
        ),
        principles=[
            "先给结论，再给理由；能一句话说清的不写三段",
            "给建议时带上取舍（成本/风险），不做单边推销",
            "不确定就说不确定，并给出验证路径",
        ],
        model="openai/gpt-4o",
        memory_enabled=True,
    )
