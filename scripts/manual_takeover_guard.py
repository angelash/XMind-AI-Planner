#!/usr/bin/env python3
"""Auto-trigger manual takeover when a task is stuck for too long."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path


TASK_RE = re.compile(r"([A-Z]+-\d{2})")


def now_ms() -> int:
    return int(time.time() * 1000)


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def append_log(log_file: Path, message: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"[{ts()}] {message}\n")


def extract_task_id(title: str | None) -> str | None:
    if not title:
        return None
    m = TASK_RE.search(title)
    return m.group(1) if m else None


def latest_runs(cur: sqlite3.Cursor, automation_id: str, limit: int = 20) -> list[tuple]:
    cur.execute(
        "SELECT status, created_at, updated_at, inbox_title "
        "FROM automation_runs WHERE automation_id = ? "
        "ORDER BY created_at DESC LIMIT ?",
        (automation_id, limit),
    )
    return cur.fetchall()


def should_trigger(
    runs: list[tuple],
    timeout_ms: int,
    pending_retry_threshold: int,
) -> tuple[bool, str | None, str]:
    if not runs:
        return False, None, "no runs found"

    status, created_at, _updated_at, title = runs[0]
    task_id = extract_task_id(title)
    age_ms = now_ms() - int(created_at or 0)

    if status == "IN_PROGRESS" and age_ms >= timeout_ms:
        reason = f"in_progress timeout: {age_ms // 60000} min"
        return True, task_id, reason

    blocked_count = 0
    blocked_task: str | None = None
    for row in runs:
        s, _c, _u, t = row
        if s != "PENDING_REVIEW":
            continue
        title_text = (t or "").lower()
        if "push blocked" not in title_text and "network blocked" not in title_text:
            continue
        blocked_count += 1
        if blocked_task is None:
            blocked_task = extract_task_id(t)
        if blocked_count >= pending_retry_threshold:
            reason = f"pending_review blocked retries: {blocked_count}"
            return True, blocked_task, reason

    return False, None, "healthy"


def write_takeover(
    queue_file: Path,
    pause_flag_file: Path,
    task_id: str | None,
    reason: str,
) -> None:
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "time": ts(),
        "task_id": task_id,
        "reason": reason,
        "status": "open",
    }
    with queue_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    pause_flag_file.write_text(
        f"triggered_at={ts()}\n"
        f"task_id={task_id or 'unknown'}\n"
        f"reason={reason}\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="C:/Users/Lenovo/.codex/sqlite/codex-dev.db")
    parser.add_argument("--automation-id", default="ai")
    parser.add_argument("--interval-sec", type=int, default=30)
    parser.add_argument("--timeout-min", type=int, default=15)
    parser.add_argument("--pending-retry-threshold", type=int, default=2)
    parser.add_argument("--log-file", default="MANUAL_TAKEOVER_GUARD.log")
    parser.add_argument("--queue-file", default="MANUAL_TAKEOVER_QUEUE.jsonl")
    parser.add_argument("--pause-flag-file", default="MANUAL_TAKEOVER.flag")
    args = parser.parse_args()

    db_path = Path(args.db)
    log_file = Path(args.log_file)
    queue_file = Path(args.queue_file)
    pause_flag_file = Path(args.pause_flag_file)
    timeout_ms = args.timeout_min * 60 * 1000
    append_log(
        log_file,
        (
            f"guard started: automation_id={args.automation_id}, "
            f"timeout={args.timeout_min}min, retry_threshold={args.pending_retry_threshold}"
        ),
    )

    while True:
        try:
            if pause_flag_file.exists():
                time.sleep(max(args.interval_sec, 5))
                continue

            conn = sqlite3.connect(str(db_path))
            try:
                cur = conn.cursor()
                runs = latest_runs(cur, args.automation_id, limit=20)
                hit, task_id, reason = should_trigger(
                    runs=runs,
                    timeout_ms=timeout_ms,
                    pending_retry_threshold=args.pending_retry_threshold,
                )
            finally:
                conn.close()

            if hit:
                write_takeover(
                    queue_file=queue_file,
                    pause_flag_file=pause_flag_file,
                    task_id=task_id,
                    reason=reason,
                )
                append_log(
                    log_file,
                    f"manual takeover triggered: task={task_id or 'unknown'}, reason={reason}",
                )
        except Exception as exc:  # noqa: BLE001
            append_log(log_file, f"error: {exc}")
        time.sleep(max(args.interval_sec, 5))


if __name__ == "__main__":
    raise SystemExit(main())
