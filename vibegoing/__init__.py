"""VibeGoing：基于 CrewAI 的本地优先 AI 伙伴工作台。"""

from .soul import Soul, SoulStore, default_soul

__all__ = ["Soul", "SoulStore", "__version__", "default_soul"]

__version__ = "0.1.0"
