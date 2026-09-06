"""权限门控（VG-305，P0 红线）：CLI Runtime 执行前的强制检查。

红线原则（PLAN.md §5.4）：CLI Agent 在本机执行任意命令的风险必须由
权限门控兜底——工作目录白名单 + 危险操作审批，**绝不静默执行**。

默认策略：
- 工作目录必须在白名单内（VIBE_ALLOWED_DIRS，os 路径分隔符分隔；
  未配置时默认仅允许当前工作目录）
- 指令中出现危险模式（rm -rf / sudo / 管道执行远程脚本等）时，
  必须经审批回调确认；无审批回调则直接拒绝
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# 危险指令模式（不区分大小写；命中即需审批）
DANGEROUS_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"rm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)", "递归强制删除"),
    (r"\bsudo\b", "提权执行"),
    (r"\bdel\s+/[a-z]*s", "Windows 递归删除"),
    (r"\bformat\b", "格式化磁盘"),
    (r"curl[^|]*\|\s*(ba)?sh", "下载并执行远程脚本"),
    (r"wget[^|]*\|\s*(ba)?sh", "下载并执行远程脚本"),
    (r"iex\s*\(|invoke-expression", "PowerShell 动态执行"),
    (r"git\s+push\s+.*--force", "强推远端"),
    (r"drop\s+(table|database)", "删除数据库对象"),
)

ApprovalCallback = Callable[[str], bool]


@dataclass
class GuardDecision:
    """门控结论。approved=False 时 reason 说明拒绝依据。"""

    approved: bool
    reason: str
    needs_approval: bool = False


class PermissionDenied(PermissionError):
    """门控拒绝：CLI Runtime 不得启动进程。"""

    def __init__(self, decision: GuardDecision):
        super().__init__(decision.reason)
        self.decision = decision


class PermissionGuard:
    """CLI Runtime 的执行前门控。"""

    def __init__(
        self,
        allowed_dirs: list[Path] | None = None,
        approval: ApprovalCallback | None = None,
    ):
        if allowed_dirs is None:
            env = os.environ.get("VIBE_ALLOWED_DIRS", "")
            raw = env.split(os.pathsep) if env else [os.getcwd()]
            allowed_dirs = [Path(p).expanduser().resolve() for p in raw if p]
        self.allowed_dirs = allowed_dirs
        self.approval = approval

    def check(self, instruction: str, workdir: Path) -> GuardDecision:
        workdir = workdir.expanduser().resolve()
        if not any(self._is_within(workdir, base) for base in self.allowed_dirs):
            allowed = "；".join(str(d) for d in self.allowed_dirs)
            return GuardDecision(
                approved=False,
                reason=f"工作目录 {workdir} 不在白名单内（允许：{allowed}）",
            )
        for pattern, label in DANGEROUS_PATTERNS:
            if re.search(pattern, instruction, flags=re.IGNORECASE):
                if self.approval is None:
                    return GuardDecision(
                        approved=False,
                        reason=f"指令含危险操作（{label}），且未配置审批通道，拒绝执行",
                        needs_approval=True,
                    )
                prompt = f"指令含危险操作（{label}）：{instruction[:120]}\n是否批准执行？"
                if not self.approval(prompt):
                    return GuardDecision(
                        approved=False, reason=f"危险操作（{label}）未获批准", needs_approval=True
                    )
                return GuardDecision(approved=True, reason=f"危险操作（{label}）已获批准")
        return GuardDecision(approved=True, reason="常规指令，目录在白名单内")

    @staticmethod
    def _is_within(child: Path, base: Path) -> bool:
        try:
            child.relative_to(base)
            return True
        except ValueError:
            return False
