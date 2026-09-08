"""SessionStart context capsule built from the portable state subset."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from . import GuardContext
from ._projectstate import parse


def _items(path: Path) -> list[dict[str, Any]]:
    values = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict): values.append(value)
    return values


def run(_: dict[str, Any], context: GuardContext) -> dict[str, Any]:
    state_path = context.project_root / "project-state.yaml"
    if not state_path.is_file(): return {"decision": "noop", "reason": "no mk-agentos project-state.yaml"}
    reads = context.evidence_dir / ".session-reads"
    if reads.parent.is_dir(): reads.write_text("", encoding="utf-8")
    state = parse(state_path); tasks = state["tasks"] if isinstance(state["tasks"], list) else []
    blocked = [task for task in tasks if isinstance(task, dict) and task.get("status") == "BLOCKED"]
    lines = [f"Project: {state.get('project', '?')} | Preset: {state.get('preset', '?')} | Tasks: {len(tasks)} | Blocked: {len(blocked)}"]
    if tasks:
        lines.append("Tasks:")
        lines.extend(f"  {task.get('id', '?')}: {task.get('status', '?')} — {task.get('name', '?')}" for task in tasks[:10] if isinstance(task, dict))
    if blocked:
        lines.append("⚠️ BLOCKED:")
        lines.extend(f"  {task.get('id', '?')}: {task.get('blocked_reason', '?')}" for task in blocked)
    attempts = _items(context.project_root / "evidence" / "attempt-log.jsonl")
    failed = [item for item in attempts if item.get("status") == "failed"]
    if failed:
        lines.append(f"⚠️ Recent failures ({len(failed)} total):")
        lines.extend(f"  {item.get('ts', '?')}: {item.get('description', item.get('attempt', '?'))}" for item in failed[-5:])
    decisions = _items(context.project_root / "evidence" / "decision-log.jsonl")
    challenges = [item for item in decisions if item.get("status") == "open" and item.get("type") == "challenge"]
    if challenges:
        lines.append("⚠️ Open challenges:")
        lines.extend(f"  {item.get('challenger', '?')}: {item.get('description', '?')}" for item in challenges[-3:])
    lines += ["Required reads (mutation locked until read):", "  1. project-state.yaml", "  2. evidence/attempt-log.jsonl"]
    if (context.project_root / "evidence" / "decision-log.jsonl").is_file(): lines.append("  3. evidence/decision-log.jsonl")
    if (context.project_root / "context-index.yaml").is_file(): lines.append("  4. context-index.yaml")
    lines.append("  ⚠️ evidence/handoff.md — read LAST (may have optimistic bias)")
    settings = getattr(context, "settings", {})
    extra = settings.get("layers", {}).get("harness", {}).get("onboarding", {}).get("extra_command") if isinstance(settings, dict) else None
    if isinstance(extra, str) and extra:
        # extra_command is trusted settings input; still bound its runtime so a
        # hung command cannot block SessionStart indefinitely.
        try:
            result = subprocess.run(extra, shell=True, cwd=context.project_root, text=True, capture_output=True, check=False, timeout=10)
            if result.returncode == 0 and result.stdout.strip(): lines.append(result.stdout.strip())
        except subprocess.TimeoutExpired:
            pass
    capsule = "\n".join(lines) + "\n"
    encoded = capsule.encode("utf-8")
    if len(encoded) > 8192: capsule = encoded[-8192:].decode("utf-8", errors="ignore")
    return {"decision": "allow", "reason": "onboarding context prepared", "context": capsule, "state_written": [str(reads)] if reads.parent.is_dir() else []}
