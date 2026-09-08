"""Deliberately small parser for the flat project-state.yaml subset.

This is not a YAML parser.  It accepts only top-level scalars and a ``tasks``
list of flat mappings, which is the portable subset guards need.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_KEY_VALUE = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z_][\w-]*):\s*(?P<value>.*?)\s*$")
_LIST_KEY_VALUE = re.compile(r"^(?P<indent>\s*)-\s*(?P<key>[A-Za-z_][\w-]*):\s*(?P<value>.*?)\s*$")


def _value(raw: str) -> str:
    value = raw.strip()
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_text(text: str) -> dict[str, object]:
    """Return top-level ``project``/``preset`` and flat ``tasks`` mappings."""
    result: dict[str, object] = {"tasks": []}
    tasks: list[dict[str, str]] = []
    in_tasks = False
    current: dict[str, str] | None = None
    task_indent = 0
    # JSON is one of the project-state file extensions.  It is intentionally
    # handled here rather than adding a YAML dependency.
    stripped = text.lstrip()
    if stripped.startswith("{"):
        decoded = json.loads(text)
        if not isinstance(decoded, dict):
            return result
        tasks_value = decoded.get("tasks", [])
        if not isinstance(tasks_value, list):
            return result
        result.update({key: decoded[key] for key in ("project", "preset") if key in decoded})
        result["tasks"] = [task for task in tasks_value if isinstance(task, dict)]
        return result
    criteria: list[dict[str, str]] | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        top = _KEY_VALUE.match(raw)
        if top and len(top.group("indent")) == 0:
            key, value = top.group("key"), _value(top.group("value"))
            if key == "tasks" and not value:
                in_tasks, current = True, None
                continue
            in_tasks = False
            if key in {"project", "preset"}:
                result[key] = value
            continue
        if not in_tasks:
            continue
        nested = _LIST_KEY_VALUE.match(raw)
        if criteria is not None and nested and len(nested.group("indent")) > task_indent:
            criteria.append({nested.group("key"): _value(nested.group("value"))})
            continue
        item = _LIST_KEY_VALUE.match(raw)
        if item:
            task_indent = len(item.group("indent"))
            current = {item.group("key"): _value(item.group("value"))}
            tasks.append(current)
            criteria = None
            continue
        child = _KEY_VALUE.match(raw)
        if current is not None and child and len(child.group("indent")) > task_indent:
            key, value = child.group("key"), _value(child.group("value"))
            if key == "acceptance_criteria" and not value:
                criteria = []
                current[key] = criteria  # type: ignore[assignment]
            else:
                current[key] = value
                criteria = None
            continue
    result["tasks"] = tasks
    return result


def parse(path: Path) -> dict[str, object]:
    """Parse a project-state file from disk."""
    return parse_text(path.read_text(encoding="utf-8"))


def replace_preset(path: Path, preset: str) -> None:
    """Replace only the top-level preset line; retain every other byte."""
    raw = path.read_text(encoding="utf-8")
    replacement = f"preset: {preset}"
    updated, count = re.subn(r"(?m)^preset:\s*\S+.*$", replacement, raw, count=1)
    if not count:
        updated = replacement + ("\n" if not raw or not raw.startswith("\n") else "") + raw
    path.write_text(updated, encoding="utf-8")
