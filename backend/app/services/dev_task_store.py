"""Development task queue service.

AUTO-01: 自动化任务队列状态机

Task status flow:
    waiting → coding → diff_ready → sync_ok → build_ok → done
    Any status → need_confirm → (after confirm) → coding
    Any status → failed → (retry) → waiting
    Any status → canceled
    done → rolled_back
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from app.core.settings import get_settings
from app.db.config import DEFAULT_MIGRATIONS_DIR
from app.db.migrate import run_migrations


# Task status constants
class TaskStatus:
    WAITING = "waiting"
    CODING = "coding"
    DIFF_READY = "diff_ready"
    SYNC_OK = "sync_ok"
    BUILD_OK = "build_ok"
    DONE = "done"
    NEED_CONFIRM = "need_confirm"
    FAILED = "failed"
    CANCELED = "canceled"
    ROLLED_BACK = "rolled_back"


# Valid status transitions
VALID_TRANSITIONS = {
    TaskStatus.WAITING: [TaskStatus.CODING, TaskStatus.CANCELED],
    TaskStatus.CODING: [TaskStatus.DIFF_READY, TaskStatus.NEED_CONFIRM, TaskStatus.FAILED, TaskStatus.CANCELED],
    TaskStatus.DIFF_READY: [TaskStatus.SYNC_OK, TaskStatus.FAILED, TaskStatus.CANCELED],
    TaskStatus.SYNC_OK: [TaskStatus.BUILD_OK, TaskStatus.FAILED, TaskStatus.CANCELED],
    TaskStatus.BUILD_OK: [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELED],
    TaskStatus.DONE: [TaskStatus.ROLLED_BACK],
    TaskStatus.NEED_CONFIRM: [TaskStatus.CODING, TaskStatus.CANCELED],
    TaskStatus.FAILED: [TaskStatus.WAITING, TaskStatus.CANCELED],
    TaskStatus.CANCELED: [],
    TaskStatus.ROLLED_BACK: [],
}


def _db_path() -> Path:
    settings = get_settings()
    path = settings.db_path_abs
    run_migrations(path, DEFAULT_MIGRATIONS_DIR)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _to_task_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "document_id": row["document_id"],
        "status": row["status"],
        "trigger_type": row["trigger_type"],
        "trigger_node_id": row["trigger_node_id"],
        "requirement": row["requirement"],
        "analysis_result": json.loads(row["analysis_result"]) if row["analysis_result"] else None,
        "coding_result": json.loads(row["coding_result"]) if row["coding_result"] else None,
        "diff_summary": row["diff_summary"],
        "sync_result": json.loads(row["sync_result"]) if row["sync_result"] else None,
        "build_result": json.loads(row["build_result"]) if row["build_result"] else None,
        "error_message": row["error_message"],
        "need_confirm_reason": row["need_confirm_reason"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
    }


def _to_artifact_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "artifact_type": row["artifact_type"],
        "file_path": row["file_path"],
        "content": row["content"],
        "created_at": row["created_at"],
    }


def list_dev_tasks(
    workspace_id: str | None = None,
    document_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List development tasks with optional filters."""
    with _connect() as conn:
        query = "SELECT * FROM dev_tasks WHERE 1=1"
        params: list[Any] = []

        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        if document_id is not None:
            query += " AND document_id = ?"
            params.append(document_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
    return [_to_task_payload(row) for row in rows]


def get_dev_task(task_id: str) -> dict[str, Any] | None:
    """Get a single development task by ID."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM dev_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    if row is None:
        return None
    return _to_task_payload(row)


def create_dev_task(
    requirement: str,
    workspace_id: str | None = None,
    document_id: str | None = None,
    trigger_type: str | None = None,
    trigger_node_id: str | None = None,
) -> dict[str, Any]:
    """Create a new development task."""
    task_id = str(uuid4())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO dev_tasks(id, workspace_id, document_id, status, trigger_type, trigger_node_id, requirement)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, workspace_id, document_id, TaskStatus.WAITING, trigger_type, trigger_node_id, requirement),
        )
    task = get_dev_task(task_id)
    if task is None:
        raise RuntimeError("created task cannot be loaded")
    return task


def update_dev_task_status(
    task_id: str,
    new_status: str,
    **fields: Any,
) -> dict[str, Any] | None:
    """Update task status with validation.

    Args:
        task_id: Task ID
        new_status: Target status (must be valid transition)
        **fields: Additional fields to update (analysis_result, coding_result, etc.)

    Returns:
        Updated task or None if not found

    Raises:
        ValueError: If transition is invalid
    """
    task = get_dev_task(task_id)
    if task is None:
        return None

    current_status = task["status"]
    if new_status not in VALID_TRANSITIONS.get(current_status, []):
        raise ValueError(
            f"Invalid status transition: {current_status} → {new_status}. "
            f"Valid transitions: {VALID_TRANSITIONS.get(current_status, [])}"
        )

    # Build update query
    updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    params: list[Any] = [new_status]

    # Handle started_at when entering coding
    if new_status == TaskStatus.CODING and current_status in (TaskStatus.WAITING, TaskStatus.NEED_CONFIRM):
        updates.append("started_at = CURRENT_TIMESTAMP")

    # Handle completed_at when entering done/failed/canceled
    if new_status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELED):
        updates.append("completed_at = CURRENT_TIMESTAMP")

    # Handle additional fields
    field_mapping = {
        "analysis_result": "analysis_result",
        "coding_result": "coding_result",
        "diff_summary": "diff_summary",
        "sync_result": "sync_result",
        "build_result": "build_result",
        "error_message": "error_message",
        "need_confirm_reason": "need_confirm_reason",
    }

    for field_name, column_name in field_mapping.items():
        if field_name in fields:
            value = fields[field_name]
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            updates.append(f"{column_name} = ?")
            params.append(value)

    params.append(task_id)

    with _connect() as conn:
        conn.execute(
            f"UPDATE dev_tasks SET {', '.join(updates)} WHERE id = ?",
            params,
        )

    return get_dev_task(task_id)


def cancel_dev_task(task_id: str) -> dict[str, Any] | None:
    """Cancel a task if it's not already done/canceled."""
    task = get_dev_task(task_id)
    if task is None:
        return None

    if task["status"] in (TaskStatus.DONE, TaskStatus.CANCELED, TaskStatus.ROLLED_BACK):
        raise ValueError(f"Cannot cancel task in status: {task['status']}")

    return update_dev_task_status(task_id, TaskStatus.CANCELED)


def retry_dev_task(task_id: str) -> dict[str, Any] | None:
    """Retry a failed task."""
    task = get_dev_task(task_id)
    if task is None:
        return None

    if task["status"] != TaskStatus.FAILED:
        raise ValueError(f"Can only retry failed tasks, current status: {task['status']}")

    return update_dev_task_status(task_id, TaskStatus.WAITING)


def confirm_dev_task(task_id: str) -> dict[str, Any] | None:
    """Confirm a task that needs confirmation."""
    task = get_dev_task(task_id)
    if task is None:
        return None

    if task["status"] != TaskStatus.NEED_CONFIRM:
        raise ValueError(f"Task does not need confirmation, current status: {task['status']}")

    return update_dev_task_status(task_id, TaskStatus.CODING)


def get_next_waiting_task() -> dict[str, Any] | None:
    """Get the next task in waiting status (FIFO)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM dev_tasks WHERE status = ? ORDER BY created_at ASC LIMIT 1",
            (TaskStatus.WAITING,),
        ).fetchone()
    if row is None:
        return None
    return _to_task_payload(row)


# Artifact operations

def create_task_artifact(
    task_id: str,
    artifact_type: str,
    file_path: str,
    content: str | None = None,
) -> dict[str, Any]:
    """Create a task artifact."""
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO task_artifacts(task_id, artifact_type, file_path, content)
            VALUES(?, ?, ?, ?)
            """,
            (task_id, artifact_type, file_path, content),
        )
        artifact_id = cursor.lastrowid

    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM task_artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError("created artifact cannot be loaded")
    return _to_artifact_payload(row)


def list_task_artifacts(task_id: str, artifact_type: str | None = None) -> list[dict[str, Any]]:
    """List artifacts for a task."""
    with _connect() as conn:
        if artifact_type:
            rows = conn.execute(
                "SELECT * FROM task_artifacts WHERE task_id = ? AND artifact_type = ? ORDER BY created_at",
                (task_id, artifact_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM task_artifacts WHERE task_id = ? ORDER BY created_at",
                (task_id,),
            ).fetchall()
    return [_to_artifact_payload(row) for row in rows]


def get_task_artifact(artifact_id: int) -> dict[str, Any] | None:
    """Get a single artifact by ID."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM task_artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
    if row is None:
        return None
    return _to_artifact_payload(row)
