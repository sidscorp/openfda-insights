#!/usr/bin/env python3
import sys
from pathlib import Path
from typing import Any

import yaml


TASKS_PATH = Path(__file__).resolve().parents[1] / "tasks.yaml"
VALID_STATUSES = {"todo", "in_progress", "completed"}


def load_tasks() -> dict[str, Any]:
    if not TASKS_PATH.exists():
        raise FileNotFoundError(f"{TASKS_PATH} not found")
    with TASKS_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if "tasks" not in data or not isinstance(data["tasks"], list):
        raise ValueError("tasks.yaml must contain a top-level 'tasks' list")
    return data


def save_tasks(data: dict[str, Any]) -> None:
    with TASKS_PATH.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def list_tasks(data: dict[str, Any]) -> None:
    for task in data["tasks"]:
        task_id = task.get("id", "UNKNOWN")
        title = task.get("title", "")
        status = task.get("status", "todo")
        priority = task.get("priority", "")
        print(f"{task_id} [{priority}] {status}: {title}")


def update_task(data: dict[str, Any], task_id: str, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Use: {', '.join(sorted(VALID_STATUSES))}")
    for task in data["tasks"]:
        if task.get("id") == task_id:
            task["status"] = status
            save_tasks(data)
            print(f"Updated {task_id} to {status}")
            return
    raise ValueError(f"Task {task_id} not found")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: manage_tasks.py list | update <TASK_ID> <STATUS>")
        raise SystemExit(1)

    command = sys.argv[1]
    data = load_tasks()

    if command == "list":
        list_tasks(data)
        return

    if command == "update":
        if len(sys.argv) != 4:
            print("Usage: manage_tasks.py update <TASK_ID> <STATUS>")
            raise SystemExit(1)
        update_task(data, sys.argv[2], sys.argv[3])
        return

    print(f"Unknown command: {command}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
