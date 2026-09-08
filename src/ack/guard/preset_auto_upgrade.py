"""Post-tool preset escalation with byte-preserving state edits."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from . import GuardContext
from ._projectstate import parse, replace_preset


def _json_lines(path):
    if not path.is_file():
        return []
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            items.append(item)
    return items


def run(_: dict[str, Any], context: GuardContext) -> dict[str, Any]:
    state_path = context.project_root / "project-state.yaml"
    if not state_path.is_file():
        return {"decision": "noop", "reason": "no mk-agentos project-state.yaml"}
    state = parse(state_path)
    current = str(state.get("preset", "standard"))
    if current == "governed":
        return {"decision": "noop", "reason": "preset already governed"}
    tasks = state["tasks"] if isinstance(state["tasks"], list) else []
    reason = ""
    if any(isinstance(task, dict) and task.get("status") == "BLOCKED" for task in tasks):
        reason = "BLOCKED task detected"
    attempts = _json_lines(context.project_root / "evidence" / "attempt-log.jsonl")
    failures = sum(1 for item in attempts if item.get("status") == "failed")
    if not reason and failures >= 2:
        reason = f"{failures} failures in attempt-log"
    progress_path = context.project_root / "evidence" / "progress.json"
    if not reason and progress_path.is_file():
        try:
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
            edits = progress.get("file_edits", {}) if isinstance(progress, dict) else {}
            maximum = max((value for value in edits.values() if isinstance(value, (int, float))), default=0) if isinstance(edits, dict) else 0
            if maximum >= 3:
                reason = f"file edited {maximum} times (rework signal)"
        except json.JSONDecodeError:
            pass
    if not reason:
        return {"decision": "allow", "reason": "no preset upgrade trigger"}
    target = "standard" if current == "light" else "governed"
    log = context.project_root / "evidence" / "decision-log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    record = {"type": "preset_upgrade", "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "from": current, "to": target, "reason": reason, "actor": "harness"}
    with log.open("a", encoding="utf-8") as out:
        out.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    replace_preset(state_path, target)
    message = f"Preset auto-upgraded: {current} → {target} (reason: {reason})"
    return {"decision": "warn", "reason": message, "state_written": [str(log), str(state_path)]}
