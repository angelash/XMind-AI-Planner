#!/usr/bin/env python3
"""Keep a Codex automation running continuously.

When no run is IN_PROGRESS, this script nudges `next_run_at` to now so the
scheduler can start the next run immediately.
"""

from __future__ import annotations

import argparse
import sqlite3
import time
from datetime import datetime
from pathlib import Path


def now_ms() -> int:
    return int(time.time() * 1000)


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def append_log(log_file: Path, message: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"[{ts()}] {message}\n")


def maybe_kick(
    db_path: Path,
    automation_id: str,
    cooldown_ms: int,
    soon_window_ms: int,
    log_file: Path,
) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT status, next_run_at, last_run_at FROM automations WHERE id = ?",
            (automation_id,),
        )
        row = cur.fetchone()
        if not row:
            append_log(log_file, f"automation '{automation_id}' not found")
            return

        status, next_run_at, _last_run_at = row
        if status != "ACTIVE":
            append_log(log_file, f"automation '{automation_id}' is not ACTIVE: {status}")
            return

        cur.execute(
            "SELECT COUNT(*) FROM automation_runs "
            "WHERE automation_id = ? AND status = 'IN_PROGRESS'",
            (automation_id,),
        )
        in_progress = int(cur.fetchone()[0])
        if in_progress > 0:
            return

        cur.execute(
            "SELECT MAX(created_at) FROM automation_runs WHERE automation_id = ?",
            (automation_id,),
        )
        latest_created = cur.fetchone()[0] or 0
        now = now_ms()

        # Avoid over-triggering while scheduler is already about to fire.
        if next_run_at is not None and next_run_at <= now + soon_window_ms:
            return

        # Avoid thrashing right after a run was created.
        if latest_created and now - int(latest_created) < cooldown_ms:
            return

        cur.execute(
            "UPDATE automations SET next_run_at = ?, updated_at = ? WHERE id = ?",
            (now, now, automation_id),
        )
        conn.commit()
        append_log(
            log_file,
            f"kicked automation '{automation_id}' (set next_run_at={now})",
        )
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        default="C:/Users/Lenovo/.codex/sqlite/codex-dev.db",
        help="Path to Codex automation sqlite DB.",
    )
    parser.add_argument("--automation-id", default="ai")
    parser.add_argument("--interval-sec", type=int, default=30)
    parser.add_argument("--cooldown-sec", type=int, default=90)
    parser.add_argument(
        "--soon-window-sec",
        type=int,
        default=30,
        help="If next_run_at is within this window, do not kick.",
    )
    parser.add_argument(
        "--log-file",
        default="AUTOMATION_WATCHDOG.log",
        help="Log file path.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    log_file = Path(args.log_file)
    cooldown_ms = args.cooldown_sec * 1000
    soon_window_ms = args.soon_window_sec * 1000

    append_log(
        log_file,
        (
            f"watchdog started: automation_id={args.automation_id}, "
            f"interval={args.interval_sec}s, cooldown={args.cooldown_sec}s"
        ),
    )

    while True:
        try:
            maybe_kick(
                db_path=db_path,
                automation_id=args.automation_id,
                cooldown_ms=cooldown_ms,
                soon_window_ms=soon_window_ms,
                log_file=log_file,
            )
        except Exception as exc:  # noqa: BLE001
            append_log(log_file, f"error: {exc}")
        time.sleep(max(args.interval_sec, 5))


if __name__ == "__main__":
    raise SystemExit(main())
