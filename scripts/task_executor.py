from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

STATUS_FLOW = ["developing", "diff_ready", "sync_ok", "build_ok", "done"]


@dataclass
class TaskState:
    id: str
    status: str
    depends_on: list[str]


def load_state(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def dump_state(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def tasks_of(data: dict[str, Any]) -> list[TaskState]:
    tasks: list[TaskState] = []
    for task in data.get("tasks", []):
        tasks.append(
            TaskState(
                id=task["id"],
                status=task["status"],
                depends_on=list(task.get("depends_on", [])),
            )
        )
    return tasks


def find_developing(tasks: list[TaskState]) -> list[str]:
    return [t.id for t in tasks if t.status == "developing"]


def find_first_ready(tasks: list[TaskState]) -> str | None:
    done = {t.id for t in tasks if t.status == "done"}
    for task in tasks:
        if task.status != "waiting":
            continue
        if all(dep in done for dep in task.depends_on):
            return task.id
    return None


def set_task_status(data: dict[str, Any], task_id: str, new_status: str) -> None:
    for task in data.get("tasks", []):
        if task.get("id") == task_id:
            task["status"] = new_status
            return
    raise KeyError(f"task not found: {task_id}")


def run_one_cycle(path: Path) -> str:
    data = load_state(path)
    tasks = tasks_of(data)

    developing = find_developing(tasks)
    if developing:
        return f"wait: developing task exists ({', '.join(developing)})"

    next_task = find_first_ready(tasks)
    if not next_task:
        return "idle: no ready waiting tasks"

    for status in STATUS_FLOW:
        set_task_status(data, next_task, status)

    dump_state(path, data)
    return f"done: {next_task}"


if __name__ == "__main__":
    default_path = Path(__file__).resolve().parents[1] / "automation_tasks.yaml"
    print(run_one_cycle(default_path))
