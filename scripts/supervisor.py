#!/usr/bin/env python3
"""Project local supervisor (守护进程) to keep dev loops running.

Keeps these processes alive:
- uvicorn backend server
- pytest loop (regression)
- dev_guard (ledger next-task notifier)

This is intentionally lightweight and local-only.
It restarts crashed subprocesses and writes logs under repo root.

Usage (recommended):
  . .venv/bin/activate
  python scripts/supervisor.py --repo-root .

You can also run inside tmux:
  tmux new -s xmind-ai -c <repo>
  . .venv/bin/activate
  python scripts/supervisor.py

NOTE:
- This does NOT implement tasks automatically.
- It is a reliability guard: "never stop" for dev support loops.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_line(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts()}] {message}\n")


@dataclass
class ManagedProc:
    name: str
    cmd: list[str]
    cwd: Path
    log_file: Path
    env: dict[str, str]
    proc: subprocess.Popen[str] | None = None
    last_start_ts: float = 0.0

    def start(self) -> None:
        self.cwd.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{ts()}] START {self.name}: {' '.join(self.cmd)}\n")
        self.proc = subprocess.Popen(
            self.cmd,
            cwd=str(self.cwd),
            stdout=self.log_file.open("a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            text=True,
            env=self.env,
        )
        self.last_start_ts = time.time()

    def poll(self) -> int | None:
        if self.proc is None:
            return None
        return self.proc.poll()

    def stop(self, timeout: float = 5.0) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is not None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def build_env(repo_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    # Ensure local imports work.
    env.setdefault("PYTHONPATH", str(repo_root / "backend"))
    return env


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--interval-sec", type=int, default=5)
    ap.add_argument("--server-port", type=int, default=8000)
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    env = build_env(repo_root)

    python = sys.executable

    procs: list[ManagedProc] = [
        ManagedProc(
            name="server",
            cmd=[
                python,
                "-m",
                "uvicorn",
                "app.main:app",
                "--app-dir",
                "backend",
                "--host",
                "0.0.0.0",
                "--port",
                str(args.server_port),
            ],
            cwd=repo_root,
            log_file=logs_dir / "server.log",
            env=env,
        ),
        ManagedProc(
            name="tests",
            cmd=[python, "-c", "import time,subprocess;\n"
                 "\n"
                 "while True:\n"
                 "    subprocess.run(['pytest','-q'], check=False)\n"
                 "    time.sleep(60)\n"],
            cwd=repo_root,
            log_file=logs_dir / "tests.log",
            env=env,
        ),
        ManagedProc(
            name="dev_guard",
            cmd=[python, "scripts/dev_guard.py", "--interval-sec", "30", "--log-file", "DEV_GUARD.log"],
            cwd=repo_root,
            log_file=logs_dir / "dev_guard.log",
            env=env,
        ),
    ]

    supervisor_log = logs_dir / "supervisor.log"
    log_line(supervisor_log, f"supervisor start repo_root={repo_root} python={python}")

    for p in procs:
        p.start()

    stopping = False

    def handle_signal(_signum: int, _frame: object) -> None:  # noqa: ANN401
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while not stopping:
        for p in procs:
            code = p.poll()
            if code is None:
                continue
            # restart with backoff
            since = time.time() - p.last_start_ts
            log_line(supervisor_log, f"proc exited: {p.name} code={code} uptime={since:.1f}s")
            time.sleep(1)
            p.start()
        time.sleep(max(args.interval_sec, 1))

    log_line(supervisor_log, "supervisor stopping")
    for p in procs:
        p.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
