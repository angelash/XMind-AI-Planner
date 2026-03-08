#!/usr/bin/env python3
"""Lightweight guard/monitor for the task ledger.

This does NOT implement tasks automatically.
It continuously reports the next READY task (first waiting task whose deps are done)
so a human/agent can keep moving without losing the thread.

Usage:
  python scripts/dev_guard.py --tasks-file automation_tasks.yaml --interval-sec 30 --log-file DEV_GUARD.log
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import time
from typing import Any

import yaml


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def next_ready_task(data: dict[str, Any]) -> tuple[str, str] | None:
    tasks = data.get("tasks", [])
    done = {t.get("id") for t in tasks if t.get("status") == "done"}
    developing = [t.get("id") for t in tasks if t.get("status") == "developing"]
    if developing:
        return (developing[0], "(developing)")

    for t in tasks:
        if t.get("status") != "waiting":
            continue
        deps = list(t.get("depends_on", []))
        if all(dep in done for dep in deps):
            return (t.get("id", ""), t.get("title", ""))
    return None


def append(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks-file", default="automation_tasks.yaml")
    ap.add_argument("--interval-sec", type=int, default=30)
    ap.add_argument("--log-file", default="DEV_GUARD.log")
    args = ap.parse_args()

    tasks_file = Path(args.tasks_file).resolve()
    log_file = Path(args.log_file).resolve()

    last: str | None = None
    append(log_file, f"[{ts()}] dev_guard started tasks_file={tasks_file}")

    while True:
        try:
            data = load_yaml(tasks_file)
            nxt = next_ready_task(data)
            if not nxt:
                cur = "IDLE"
            else:
                cur = f"NEXT {nxt[0]} {nxt[1]}"
            if cur != last:
                append(log_file, f"[{ts()}] {cur}")
                last = cur
        except Exception as exc:  # noqa: BLE001
            append(log_file, f"[{ts()}] ERROR {exc}")
        time.sleep(max(args.interval_sec, 5))


if __name__ == "__main__":
    raise SystemExit(main())
