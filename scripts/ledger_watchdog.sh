#!/usr/bin/env bash
set -euo pipefail

# A tiny "activity" watchdog: shows what the next ready task is and whether
# there are unpushed commits.
#
# It does NOT modify code. It is meant to make it obvious if the dev loop is idle.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

while true; do
  echo "[$(date '+%F %T')] next task (from DEV_GUARD.log): $(tail -n 1 DEV_GUARD.log 2>/dev/null || echo 'n/a')"
  git fetch origin -q || true
  echo "[$(date '+%F %T')] git: $(git rev-list --left-right --count origin/main...main 2>/dev/null | tr '\t' ' ' || echo 'n/a') (behind ahead)"
  sleep 30
done
