#!/usr/bin/env python3
"""Auto-trigger manual takeover when a task is stuck for too long."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from urllib import error, request


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

    # If task is actively running and still within timeout, do not evaluate
    # historical PENDING_REVIEW records.
    if status == "IN_PROGRESS":
        if age_ms >= timeout_ms:
            reason = f"in_progress timeout: {age_ms // 60000} min"
            return True, task_id, reason
        return False, None, "healthy in_progress"

    # Count only consecutive latest blocked reviews of the same task.
    blocked_count = 0
    blocked_task: str | None = None
    for s, _c, _u, t in runs:
        if s != "PENDING_REVIEW":
            break
        title_text = (t or "").lower()
        if "push blocked" not in title_text and "network blocked" not in title_text:
            break
        current_task = extract_task_id(t)
        if blocked_task is None:
            blocked_task = current_task
        elif current_task != blocked_task:
            break
        blocked_count += 1
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


def send_feishu_text(webhook_url: str, text: str) -> tuple[bool, str]:
    payload = {
        "msg_type": "text",
        "content": {
            "text": text,
        },
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return True, body
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return False, f"http_error={exc.code}, body={body}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


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
    parser.add_argument(
        "--feishu-webhook-env",
        default="FEISHU_WEBHOOK_URL",
        help="Environment variable name that stores Feishu bot webhook url.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    log_file = Path(args.log_file)
    queue_file = Path(args.queue_file)
    pause_flag_file = Path(args.pause_flag_file)
    feishu_webhook_url = os.getenv(args.feishu_webhook_env, "").strip()
    timeout_ms = args.timeout_min * 60 * 1000
    append_log(
        log_file,
        (
            f"guard started: automation_id={args.automation_id}, "
            f"timeout={args.timeout_min}min, retry_threshold={args.pending_retry_threshold}"
        ),
    )
    if not feishu_webhook_url:
        append_log(
            log_file,
            (
                f"feishu webhook not configured, set env {args.feishu_webhook_env} "
                "to enable notifications"
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
                if feishu_webhook_url:
                    text = (
                        "[XMind-AI-Planner] 触发人工接管\n"
                        f"任务: {task_id or 'unknown'}\n"
                        f"原因: {reason}\n"
                        f"时间: {ts()}\n"
                        "动作: 已创建 MANUAL_TAKEOVER.flag 并暂停自动触发"
                    )
                    ok, result = send_feishu_text(feishu_webhook_url, text)
                    if ok:
                        append_log(log_file, "feishu notification sent")
                    else:
                        append_log(log_file, f"feishu notification failed: {result}")
        except Exception as exc:  # noqa: BLE001
            append_log(log_file, f"error: {exc}")
        time.sleep(max(args.interval_sec, 5))


if __name__ == "__main__":
    raise SystemExit(main())
