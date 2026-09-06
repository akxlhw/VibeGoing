"""会话持久化：跨进程恢复对话（VG-101）。

基于 CrewAI 的 SQLiteFlowPersistence 快照库（flow_states 表）。
TeammateFlow 挂载 persistence 后，handle_turn 按 session_id 自动
恢复最新快照；本模块提供会话的列举与解析（供 --resume/--list-sessions）。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SessionInfo:
    """一条历史会话的摘要信息。"""

    session_id: str
    updated_at: str
    message_count: int
    preview: str


class SessionStore:
    """读取 CrewAI flow_states 快照库，列出与解析历史会话。"""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def list_sessions(self, limit: int = 20) -> list[SessionInfo]:
        """按最近活跃排序列出会话摘要。"""
        if not self.db_path.exists():
            return []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT flow_uuid, MAX(timestamp) AS ts
                FROM flow_states GROUP BY flow_uuid ORDER BY ts DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            sessions = []
            for flow_uuid, ts in rows:
                state_json = conn.execute(
                    """
                    SELECT state_json FROM flow_states
                    WHERE flow_uuid = ? ORDER BY id DESC LIMIT 1
                    """,
                    (flow_uuid,),
                ).fetchone()
                if state_json is None:
                    continue
                sessions.append(_to_session_info(flow_uuid, str(ts), state_json[0]))
        return sessions

    def messages(self, session_id: str, limit: int = 200) -> list[dict]:
        """读取某会话最新快照的消息列表（供 UI 恢复聊天记录）。"""
        if not self.db_path.exists():
            return []
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT state_json FROM flow_states WHERE flow_uuid = ? ORDER BY id DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        if row is None:
            return []
        try:
            state = json.loads(row[0])
            return [
                {"role": m.get("role"), "content": str(m.get("content", ""))}
                for m in state.get("messages", [])[:limit]
            ]
        except (json.JSONDecodeError, AttributeError):
            return []

    def resolve(self, session_id: str | None) -> str | None:
        """解析 --resume 的目标：None/空 → 最近会话；否则精确或唯一前缀匹配。"""
        sessions = self.list_sessions()
        if not sessions:
            return None
        if not session_id:
            return sessions[0].session_id
        exact = next((s.session_id for s in sessions if s.session_id == session_id), None)
        if exact is not None:
            return exact
        prefixed = [s.session_id for s in sessions if s.session_id.startswith(session_id)]
        return prefixed[0] if len(prefixed) == 1 else None


def _to_session_info(flow_uuid: str, ts: str, state_json: str) -> SessionInfo:
    try:
        state = json.loads(state_json)
        messages = state.get("messages", [])
        preview = next(
            (str(m.get("content", "")) for m in messages if m.get("role") == "user"),
            "",
        )
        preview = preview[:40] + ("…" if len(preview) > 40 else "")
    except (json.JSONDecodeError, AttributeError):
        messages, preview = [], ""
    return SessionInfo(
        session_id=flow_uuid,
        updated_at=ts,
        message_count=len(messages),
        preview=preview,
    )
