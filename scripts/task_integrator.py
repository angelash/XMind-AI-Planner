#!/usr/bin/env python3
"""Auto-integrate task commits from Codex worktrees into main.

By default this script cherry-picks and pushes to origin/main.
Use `--no-push` to keep local-only integration.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import re
import subprocess
import time


TASK_SUBJECT_RE = re.compile(r"^chore\(task\): complete ([A-Z]+-\d+)$")


def run(cmd: list[str], check: bool = True) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=check)
    return proc.stdout.strip()


def log_line(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def get_worktrees(repo_root: Path) -> list[Path]:
    out = run(["git", "-C", str(repo_root), "worktree", "list", "--porcelain"])
    result: list[Path] = []
    for line in out.splitlines():
        if line.startswith("worktree "):
            result.append(Path(line.split(" ", 1)[1]))
    return result


def list_candidate_commits(main_repo: Path, wt: Path) -> list[tuple[int, str, str]]:
    # commits in wt that are not in main branch head
    out = run(
        [
            "git",
            "-C",
            str(wt),
            "log",
            "--pretty=format:%ct%x09%H%x09%s",
            "main..HEAD",
        ],
        check=False,
    )
    if not out:
        return []
    rows: list[tuple[int, str, str]] = []
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        ts, sha, subject = parts
        if TASK_SUBJECT_RE.match(subject):
            rows.append((int(ts), sha, subject))
    return rows


def main_contains_subject(repo_root: Path, subject: str) -> bool:
    out = run(
        [
            "git",
            "-C",
            str(repo_root),
            "log",
            "--pretty=format:%s",
            "-n",
            "200",
        ]
    )
    return subject in out.splitlines()


def sync_worktrees_to_main(repo_root: Path, worktrees: list[Path], log_path: Path) -> None:
    for wt in worktrees:
        if wt == repo_root:
            continue
        if not wt.exists():
            continue
        run(["git", "-C", str(wt), "fetch", "origin", "--prune"], check=False)
        run(["git", "-C", str(wt), "reset", "--hard", "origin/main"], check=False)
        run(
            [
                "git",
                "-C",
                str(wt),
                "remote",
                "set-url",
                "origin",
                "https://github.com/angelash/XMind-AI-Planner.git",
            ],
            check=False,
        )
    log_line(log_path, "worktrees synchronized to origin/main")


def integrate_one(repo_root: Path, log_path: Path, *, push: bool) -> bool:
    worktrees = get_worktrees(repo_root)
    candidates: list[tuple[int, Path, str, str]] = []
    for wt in worktrees:
        if wt == repo_root or not wt.exists():
            continue
        for ts, sha, subject in list_candidate_commits(repo_root, wt):
            candidates.append((ts, wt, sha, subject))

    if not candidates:
        return False

    candidates.sort(key=lambda x: x[0])
    for _ts, wt, sha, subject in candidates:
        if main_contains_subject(repo_root, subject):
            log_line(log_path, f"skip duplicate subject: {subject} ({sha[:7]})")
            continue
        try:
            run(["git", "-C", str(repo_root), "cherry-pick", sha])
        except subprocess.CalledProcessError:
            run(["git", "-C", str(repo_root), "cherry-pick", "--abort"], check=False)
            log_line(log_path, f"cherry-pick failed: {sha[:7]} from {wt}")
            continue

        if push:
            try:
                run(["git", "-C", str(repo_root), "push", "origin", "main"])
            except subprocess.CalledProcessError as exc:
                log_line(log_path, f"push failed after cherry-pick {sha[:7]}: {exc}")
                return False
        else:
            log_line(log_path, f"integrated locally (manual push required): {subject} ({sha[:7]})")

        if push:
            log_line(log_path, f"integrated and pushed {subject} from {wt} ({sha[:7]})")
        return True

    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="F:/workspace/github/XMind-AI-Planner")
    parser.add_argument("--interval-sec", type=int, default=20)
    parser.add_argument("--sync-every-sec", type=int, default=300)
    parser.add_argument("--log-file", default="TASK_INTEGRATOR.log")
    parser.add_argument(
        "--push",
        dest="push",
        action="store_true",
        default=True,
        help="Push origin/main after each integration (default: on)",
    )
    parser.add_argument(
        "--no-push",
        dest="push",
        action="store_false",
        help="Disable pushing; integrate into local main only.",
    )
    return parser.parse_args()


def loop(args: argparse.Namespace) -> None:
    repo_root = Path(args.repo_root).resolve()
    log_path = repo_root / args.log_file
    log_line(log_path, f"task integrator started (push={'on' if args.push else 'off'})")
    last_sync = 0.0
    while True:
        now = time.time()
        if now - last_sync >= max(args.sync_every_sec, 60):
            sync_worktrees_to_main(repo_root, get_worktrees(repo_root), log_path)
            last_sync = now
        changed = integrate_one(repo_root, log_path, push=args.push)
        if not changed:
            time.sleep(max(args.interval_sec, 5))


if __name__ == "__main__":
    loop(parse_args())
