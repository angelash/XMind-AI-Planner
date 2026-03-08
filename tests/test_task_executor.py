from pathlib import Path

import yaml

from scripts.task_executor import run_one_cycle


def write_tasks(path: Path, tasks: list[dict]) -> None:
    payload = {
        "project": "x",
        "tasks": tasks,
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_cycle_waits_on_developing(tmp_path: Path) -> None:
    path = tmp_path / "tasks.yaml"
    write_tasks(
        path,
        [
            {"id": "A", "depends_on": [], "status": "developing"},
            {"id": "B", "depends_on": ["A"], "status": "waiting"},
        ],
    )

    message = run_one_cycle(path)
    assert message.startswith("wait:")


def test_cycle_advances_first_ready(tmp_path: Path) -> None:
    path = tmp_path / "tasks.yaml"
    write_tasks(
        path,
        [
            {"id": "A", "depends_on": [], "status": "done"},
            {"id": "B", "depends_on": ["A"], "status": "waiting"},
            {"id": "C", "depends_on": [], "status": "waiting"},
        ],
    )

    message = run_one_cycle(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert message == "done: B"
    status_map = {task["id"]: task["status"] for task in data["tasks"]}
    assert status_map["B"] == "done"
    assert status_map["C"] == "waiting"


def test_git_policy_commit_only_default() -> None:
    data = yaml.safe_load(Path("automation_tasks.yaml").read_text(encoding="utf-8"))
    assert data["git_policy"]["commit_push_on_each_task_done"] is False
