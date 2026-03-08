# 自动化运行手册（连续执行 + 15 分钟超时自动接管）

## 1. 真相源
- 代码真相源：`origin/main`
- 任务真相源：`automation_tasks.yaml`
- 原则：以主干和任务台账为准，禁止重复执行已 `done` 任务。

## 2. 常驻进程
- `automation_watchdog.py`：持续触发下一轮自动化
- `task_integrator.py`：把 worktree 任务提交集成到 `main` 并推送
- `manual_takeover_guard.py`：超时自动触发人工接管

## 3. 启动命令
```powershell
python scripts/automation_watchdog.py --automation-id ai --interval-sec 10 --cooldown-sec 30 --soon-window-sec 10 --log-file AUTOMATION_WATCHDOG.log --pause-flag-file MANUAL_TAKEOVER.flag
python scripts/task_integrator.py --repo-root F:/workspace/github/XMind-AI-Planner --interval-sec 20 --sync-every-sec 180 --log-file TASK_INTEGRATOR.log
python scripts/manual_takeover_guard.py --automation-id ai --interval-sec 30 --timeout-min 15 --pending-retry-threshold 2 --log-file MANUAL_TAKEOVER_GUARD.log --queue-file MANUAL_TAKEOVER_QUEUE.jsonl --pause-flag-file MANUAL_TAKEOVER.flag --feishu-webhook-env FEISHU_WEBHOOK_URL
```

飞书通知配置：
```powershell
$env:FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"
```
说明：未配置该环境变量时，守护脚本仅写本地日志，不发送飞书消息。

## 4. 自动接管触发规则（默认）
- 规则 A：最新运行为 `IN_PROGRESS` 且持续时间 > 15 分钟
- 规则 B：最近运行中出现 `PENDING_REVIEW` 且标题含 `push blocked`/`network blocked`，累计 >= 2 次

命中任一规则后：
- 创建 `MANUAL_TAKEOVER.flag`（暂停 watchdog 继续 kick）
- 记录 `MANUAL_TAKEOVER_QUEUE.jsonl` 待处理项
- 记录 `MANUAL_TAKEOVER_GUARD.log` 触发原因
- 若已配置 `FEISHU_WEBHOOK_URL`，自动发送飞书告警消息

## 5. 人工接管处理步骤
1. 根据 `MANUAL_TAKEOVER_QUEUE.jsonl` 找到任务 ID 和原因。
2. 从对应 worktree 抽取 `chore(task): complete TASK-ID` 提交，`cherry-pick` 到 `main`。
3. 跑任务最小测试集，确认通过后 `git push origin main`。
4. 更新 `automation_tasks.yaml` 为正确状态（`done`），修正任何误标。
5. 全量同步 worktree 到 `origin/main`。
6. 删除 `MANUAL_TAKEOVER.flag`，恢复 watchdog 自动触发。

## 6. 观测文件
- `AUTOMATION_WATCHDOG.log`
- `TASK_INTEGRATOR.log`
- `MANUAL_TAKEOVER_GUARD.log`
- `MANUAL_TAKEOVER_QUEUE.jsonl`

## 7. Commit-only mode (manual push)
- Default policy: automation commits only and does not auto-push.
- `automation_tasks.yaml`: `git_policy.commit_push_on_each_task_done: false`.
- If you want integrator to push automatically, start it with `--push`; otherwise keep default off.

Recommended commands (manual push workflow):
```powershell
python scripts/task_executor.py --tasks-file automation_tasks.yaml --git-commit
python scripts/task_integrator.py --repo-root F:/workspace/github/XMind-AI-Planner --interval-sec 20 --sync-every-sec 180 --log-file TASK_INTEGRATOR.log
```

## 8. Anti-loop guardrails
- `task_integrator.py` now defaults to push mode (`push=on`). Use `--no-push` only for debugging.
- `automation_watchdog.py` can auto-clear stale `MANUAL_TAKEOVER.flag` when the flagged task is already `done`.
- `manual_takeover_guard.py` can auto-close stale open queue items when the flagged task is already `done`.
- Always pass absolute paths for `--pause-flag-file`, `--queue-file`, and `--log-file` in long-running processes.
