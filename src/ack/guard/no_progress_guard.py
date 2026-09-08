"""PreToolUse no-progress gate backed by progress.json v2."""
from __future__ import annotations

import json
import os
from typing import Any

from . import GuardContext
from .progress_tracker import TEST_RE, compact_sorted, excluded, hash16


def _threshold(context: GuardContext, key: str, env: str, default: int) -> int:
    value = os.environ.get(env)
    if value is None:
        value = getattr(context, "settings", {}).get("layers", {}).get("harness", {}).get("no_progress", {}).get(key, default)
    try: return int(value)
    except (TypeError, ValueError): return default


def run(payload: dict[str, Any], context: GuardContext) -> dict[str, Any]:
    target = context.evidence_dir / "progress.json"
    if not target.is_file(): return {"decision": "noop", "reason": "progress tracker unavailable"}
    session = payload.get("session_id", payload.get("sessionId", ""))
    if not isinstance(session, str) or not session: return {"decision": "noop", "reason": "missing session identity"}
    try: entry = json.loads(target.read_text(encoding="utf-8")).get("sessions", {}).get(session, {})
    except json.JSONDecodeError: return {"decision": "noop", "reason": "progress tracker unreadable"}
    name, data = payload.get("tool_name", ""), payload.get("tool_input")
    data = data if isinstance(data, dict) else {}
    path = data.get("file_path", data.get("path", ""))
    if name in {"Edit", "Write"} and isinstance(path, str) and path and not excluded(path):
        count = entry.get("file_edits", {}).get(path, 0); block = _threshold(context, "edit_block", "MK_NO_PROGRESS_EDIT_BLOCK", 12); warn = _threshold(context, "edit_warn", "MK_NO_PROGRESS_EDIT_WARN", 6)
        if count >= block: return {"decision": "deny", "reason": f"BLOCKED: File '{path}' has been modified {count} times this session. Likely stuck — stop and report BLOCKED to the human operator. (harness no-progress-guard, threshold: {block})"}
        if count >= warn: return {"decision": "warn", "reason": f"WARNING: File '{path}' modified {count} times. Consider whether you're making progress. (harness no-progress-guard)"}
    if data:
        count = entry.get("call_hashes", {}).get(hash16(f"{name}:" + compact_sorted(data)), 0); block = _threshold(context, "call_block", "MK_NO_PROGRESS_CALL_BLOCK", 3)
        if count >= block: return {"decision": "deny", "reason": f"BLOCKED: Identical tool call executed {count} times. You are in a loop — change approach or report BLOCKED. (harness no-progress-guard, threshold: {block})"}
    command = data.get("command", "")
    if name == "Bash" and isinstance(command, str) and TEST_RE.search(command):
        failures = entry.get("failure_by_command", {}).get(hash16(command), {}).get("failure_hashes", {}).values(); maximum = max(failures, default=0); warn = _threshold(context, "fail_warn", "MK_NO_PROGRESS_FAIL_WARN", 2)
        if maximum >= warn: return {"decision": "warn", "reason": f"WARNING: Same test failure occurred {maximum} times for this exact command. Re-check state changes and assumptions before retrying. Shadow-only policy does not block this call. (harness no-progress-guard, cmd: {command})"}
    return {"decision": "allow", "reason": "progress guard passed"}
