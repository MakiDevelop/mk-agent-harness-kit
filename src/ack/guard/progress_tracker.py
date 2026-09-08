"""PostToolUse counters, byte-compatible with legacy progress.json v2."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from . import GuardContext

TEST_RE = __import__("re").compile(r"(pytest|npm test|npm run test|jest|mocha|ruff|mypy|tsc|make test|go test|cargo test)", __import__("re").I)


def compact_sorted(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def excluded(path: str) -> bool:
    return "/evidence/" in path or path.endswith("/progress.json") or path.endswith("/vault.jsonl")


def run(payload: dict[str, Any], context: GuardContext) -> dict[str, Any]:
    session = payload.get("session_id", payload.get("sessionId", ""))
    if not isinstance(session, str) or not session:
        return {"decision": "noop", "reason": "missing session identity"}
    context.evidence_dir.mkdir(parents=True, exist_ok=True)
    target = context.evidence_dir / "progress.json"
    lock = context.evidence_dir / ".progress.lock"
    with lock.open("a+") as handle:
        if sys.platform != "win32":
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            try:
                state = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"schema_version": 2, "sessions": {}}
            except json.JSONDecodeError:
                state = {"schema_version": 2, "sessions": {}}
            state["schema_version"] = 2
            sessions = state.setdefault("sessions", {})
            entry = sessions.setdefault(session, {"file_edits": {}, "failure_by_command": {}, "call_hashes": {}})
            for key in ("file_edits", "failure_by_command", "call_hashes"):
                entry.setdefault(key, {})
            name = payload.get("tool_name", "")
            tool_input = payload.get("tool_input")
            tool_input = tool_input if isinstance(tool_input, dict) else {}
            path = tool_input.get("file_path", tool_input.get("path", ""))
            if name in {"Edit", "Write"} and isinstance(path, str) and path and not excluded(path):
                entry["file_edits"][path] = entry["file_edits"].get(path, 0) + 1
            raw_response = payload.get("tool_response")
            response: dict[str, Any] = raw_response if isinstance(raw_response, dict) else {}
            command = tool_input.get("command", "")
            # Legacy parity with jq's `// default`: an explicit JSON null falls
            # back to the default, it does not become the string "None".
            raw_exit = response.get("exit_code")
            exit_code = "0" if raw_exit is None else str(raw_exit)
            raw_stderr = response.get("stderr")
            stderr = "" if raw_stderr is None else str(raw_stderr)
            if name == "Bash" and exit_code != "0" and isinstance(command, str) and TEST_RE.search(command):
                cmd_hash, fail_hash = hash16(command), hash16(f"{exit_code}:{stderr}")
                failure = entry["failure_by_command"].setdefault(cmd_hash, {"command": command, "failure_hashes": {}})
                failure["command"] = command
                hashes = failure.setdefault("failure_hashes", {})
                hashes[fail_hash] = hashes.get(fail_hash, 0) + 1
            if tool_input:
                call_hash = hash16(f"{name}:" + compact_sorted(tool_input))
                entry["call_hashes"][call_hash] = entry["call_hashes"].get(call_hash, 0) + 1
            temporary = target.with_name(target.name + ".tmp")
            temporary.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
            temporary.replace(target)
        finally:
            if sys.platform != "win32":
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {"decision": "allow", "reason": "progress recorded", "state_written": [str(target)]}
