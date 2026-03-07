# 自动化运行说明（连续执行直到完成）

## 1. 目标

对 `automation_tasks.yaml` 中的任务持续调度，直到全部任务为 `done`，且 `REL-01` 完成。

## 2. 调度规则

1. 每次轮询先检查是否存在 `developing` 任务。
2. 若存在 `developing`：本轮不启动新任务，直接等待下一轮。
3. 若不存在 `developing`：选择第一个依赖已满足且状态为 `waiting` 的任务，推进到 `done`。
4. 任务状态推进顺序：`developing -> diff_ready -> sync_ok -> build_ok -> done`。
5. 失败任务标记为 `failed`，重试后仍失败则转 `need_confirm`。
6. 每完成一个任务，必须立即执行一次 `git commit` 和 `git push`。
7. 所有任务完成并通过 `REL-01` 后停止调度。

补充执行机制：

- 自动化在 worktree 内完成任务提交。
- `scripts/task_integrator.py` 负责将这些任务提交自动集成到主工作区并推送 `main`。
- 若自动化侧 push 受限，集成器会继续保证“一任务一提交一推送”在主干落地。

## 3. 轮询与节奏

- 轮询周期：5 分钟（若使用 watchdog，则无空窗接力）。
- 不区分白天/夜晚，持续执行。

## 4. 人工确认触发点

1. 连续失败或不可恢复异常。
2. 高风险操作（大规模覆盖或删除）。
3. 依赖冲突导致无法自动推进。
