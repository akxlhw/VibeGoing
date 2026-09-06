"""任务台账（VG-205）：协作任务的执行记录与产物归档。

SQLite 双表：crew_tasks（任务头，状态机 pending/running/done/failed）
与 crew_stages（每个协作阶段的产物）。全部本地存储于 VIBE_HOME/ledger.db。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

TASK_STATUSES = ("pending", "running", "done", "failed")


@dataclass
class TaskRecord:
    task_id: str
    description: str
    mode: str
    status: str
    created_at: str
    updated_at: str


@dataclass
class StageRecord:
    stage_id: int
    task_id: str
    stage: str
    agent: str
    output: str
    created_at: str


class TaskLedger:
    """协作任务台账：创建任务、记录阶段产物、状态流转与查询。"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Windows 时钟毫秒粒度约 15ms，快速操作可能拿到同一时间戳；
        # 维护实例级单调时间戳保证"最近活跃排序"稳定
        self._last_ts = ""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS crew_tasks (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS crew_stages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    output TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _now(self) -> str:
        """严格递增的毫秒时间戳：与上次相同或更早时补 1ms。"""
        ts = datetime.now().isoformat(timespec="milliseconds")
        if ts <= self._last_ts:
            ts = (datetime.fromisoformat(self._last_ts) + timedelta(milliseconds=1)).isoformat(
                timespec="milliseconds"
            )
        self._last_ts = ts
        return ts

    def create_task(self, description: str, mode: str) -> TaskRecord:
        now = self._now()
        record = TaskRecord(
            task_id=uuid4().hex[:8],
            description=description,
            mode=mode,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO crew_tasks VALUES (?, ?, ?, ?, ?, ?)",
                (record.task_id, description, mode, record.status, now, now),
            )
        return record

    def set_status(self, task_id: str, status: str) -> TaskRecord:
        """流转状态并返回刷新后的任务记录。"""
        if status not in TASK_STATUSES:
            raise ValueError(f"非法状态 {status}，允许值：{TASK_STATUSES}")
        now = self._now()
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE crew_tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, task_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"任务不存在：{task_id}")
        refreshed = self.get(task_id)
        assert refreshed is not None  # UPDATE 成功则任务必然存在
        return refreshed[0]

    def add_stage(self, task_id: str, stage: str, agent: str, output: str) -> StageRecord:
        now = self._now()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO crew_stages (task_id, stage, agent, output, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (task_id, stage, agent, output, now),
            )
            conn.execute("UPDATE crew_tasks SET updated_at = ? WHERE id = ?", (now, task_id))
            return StageRecord(cur.lastrowid or 0, task_id, stage, agent, output, now)

    def get(self, task_id: str) -> tuple[TaskRecord, list[StageRecord]] | None:
        """按 ID（支持唯一前缀）取任务与其全部阶段。"""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM crew_tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                rows = conn.execute(
                    "SELECT * FROM crew_tasks WHERE id LIKE ?", (task_id + "%",)
                ).fetchall()
                if len(rows) != 1:
                    return None
                row = rows[0]
            task = TaskRecord(*row)
            stages = [
                StageRecord(*r)
                for r in conn.execute(
                    "SELECT id, task_id, stage, agent, output, created_at "
                    "FROM crew_stages WHERE task_id = ? ORDER BY id",
                    (task.task_id,),
                )
            ]
        return task, stages

    def list_tasks(self, limit: int = 20) -> list[TaskRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, description, mode, status, created_at, updated_at "
                "FROM crew_tasks ORDER BY updated_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [TaskRecord(*r) for r in rows]
