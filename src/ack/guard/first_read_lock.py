"""PreToolUse first-read lock without a YAML dependency."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any
from . import GuardContext

READ_ONLY = re.compile(r"^(?:ls|cat|head|tail|wc|grep|find|echo|pwd)(?:\s|$)|^git (?:log|status|diff)(?:\s|$)")
PRESET = re.compile(r"^preset:\s*(\S+)", re.MULTILINE)

def run(payload: dict[str, Any], context: GuardContext) -> dict[str, Any]:
    tool = payload.get("tool_name")
    raw_input = payload.get("tool_input")
    tool_input: dict[str, Any] = raw_input if isinstance(raw_input, dict) else {}
    if tool not in {"Edit", "Write", "Bash"}:
        return {"decision": "noop", "reason": "not a mutation tool"}
    if tool == "Bash" and READ_ONLY.match(str(tool_input.get("command", ""))):
        return {"decision": "allow", "reason": "read-only Bash command"}
    state = context.project_root / "project-state.yaml"
    if not state.is_file():
        return {"decision": "allow", "reason": "no mk-agentos project-state.yaml"}
    match = PRESET.search(state.read_text(encoding="utf-8"))
    preset = match.group(1) if match else "standard"
    if preset == "light":
        return {"decision": "allow", "reason": "light preset"}
    # Legacy parity (first-read-lock.sh): project-state is always required; the
    # logs are required only when they exist and are non-empty; context-index
    # only when it exists. A missing optional file never blocks by itself.
    def _nonempty(path: Path) -> bool:
        return path.is_file() and path.stat().st_size > 0

    required = [state]
    attempt = context.project_root / "evidence" / "attempt-log.jsonl"
    if _nonempty(attempt):
        required.append(attempt)
    if preset == "governed":
        decision = context.project_root / "evidence" / "decision-log.jsonl"
        if _nonempty(decision):
            required.append(decision)
        context_index = context.project_root / "context-index.yaml"
        if context_index.is_file():
            required.append(context_index)
    reads_file = context.evidence_dir / ".session-reads"
    reads = reads_file.read_text(encoding="utf-8").splitlines() if reads_file.is_file() else []
    missing = []
    for path in required:
        read = any(str(path) == item or path.name == Path(item).name for item in reads)
        if not read:
            missing.append(str(path.relative_to(context.project_root)))
    if missing:
        return {"decision": "deny", "reason": "missing required reads: " + ", ".join(missing), "context": f"preset: {preset}"}
    return {"decision": "allow", "reason": "required files read", "context": f"preset: {preset}"}
