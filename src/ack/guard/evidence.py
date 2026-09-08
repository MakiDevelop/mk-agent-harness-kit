"""Evidence vault state location, append, and chain verification."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import GuardContext


def _project_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(os.environ["CLAUDE_PROJECT_DIR"]).resolve()
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
        if out:
            return Path(out).resolve()
    except (OSError, subprocess.CalledProcessError):
        pass
    return Path.cwd().resolve()


def context_from_args(project_root: str | None, settings: str | None) -> GuardContext:
    root = _project_root(project_root)
    configured: str | None = None
    if settings:
        settings_path = Path(settings)
        if not settings_path.is_file():
            raise ValueError(f"settings not found: {settings}")
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
        configured = raw.get("layers", {}).get("harness", {}).get("evidence_dir")
        if configured is not None and not isinstance(configured, str):
            raise ValueError("layers.harness.evidence_dir must be a string")
    chosen = os.environ.get("ACK_EVIDENCE_DIR") or configured
    evidence_dir = Path(chosen).expanduser() if chosen else root / ".mk-agentos" / "evidence"
    if not evidence_dir.is_absolute():
        evidence_dir = root / evidence_dir
    return GuardContext(root, evidence_dir.resolve())


def _string(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _body(payload: dict[str, Any], previous: str) -> dict[str, Any]:
    response = payload.get("tool_response")
    response = response if isinstance(response, dict) else {}
    tool_input = payload.get("tool_input")
    return {
        "ts": os.environ.get("ACK_GUARD_TIMESTAMP") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": _string(payload.get("session_id"), "unknown"),
        "tool": _string(payload.get("tool_name"), "unknown"),
        "input": tool_input if isinstance(tool_input, (dict, list, str, int, float, bool)) else {},
        "exit_code": _string(response.get("exit_code"), "n/a"),
        # ``pwd`` in the legacy shell hook preserves macOS's /var symlink; retain
        # that logical spelling so old and new records hash identically.
        "cwd": os.environ.get("PWD") or os.getcwd(),
        "prev_hash": previous,
    }


def _compact(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def run(payload: dict[str, Any], context: GuardContext) -> dict[str, Any]:
    context.evidence_dir.mkdir(parents=True, exist_ok=True)
    vault = context.evidence_dir / "vault.jsonl"
    lock = context.evidence_dir / ".vault.lock"
    with lock.open("a+") as lock_handle:
        if sys.platform != "win32":
            import fcntl
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        previous = "genesis"
        if vault.is_file() and vault.stat().st_size:
            try:
                previous = json.loads(vault.read_text(encoding="utf-8").splitlines()[-1]).get("hash", "genesis")
            except (json.JSONDecodeError, IndexError):
                previous = "genesis"
        body = _body(payload, previous)
        digest = hashlib.sha256(_compact(body).encode("utf-8")).hexdigest()
        record = {**body, "hash": digest}
        with vault.open("a", encoding="utf-8") as out:
            out.write(_compact(record) + "\n")
        if sys.platform != "win32":
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    return {"decision": "allow", "reason": "evidence recorded", "state_written": [str(vault)]}


def verify(vault: Path) -> int:
    previous = "genesis"
    if not vault.is_file():
        print(f"vault not found: {vault}", file=sys.stderr)
        return 1
    for line_no, line in enumerate(vault.read_text(encoding="utf-8").splitlines(), 1):
        try:
            record = json.loads(line)
            recorded = record.pop("hash")
            expected = hashlib.sha256(_compact(record).encode("utf-8")).hexdigest()
            if record.get("prev_hash") != previous or recorded != expected:
                raise ValueError("previous hash or record hash mismatch")
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            print(f"vault verification failed at line {line_no}: {exc}", file=sys.stderr)
            return 1
        previous = recorded
    print(f"vault verified: {vault}")
    return 0
