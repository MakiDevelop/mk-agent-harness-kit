"""PostToolUse Read tracker."""
from __future__ import annotations
from typing import Any
from . import GuardContext

def run(payload: dict[str, Any], context: GuardContext) -> dict[str, Any]:
    tool_input = payload.get("tool_input")
    path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if payload.get("tool_name") != "Read" or not isinstance(path, str) or not path:
        return {"decision": "noop", "reason": "not a Read with file_path"}
    context.evidence_dir.mkdir(parents=True, exist_ok=True)
    reads = context.evidence_dir / ".session-reads"
    with reads.open("a", encoding="utf-8") as out:
        out.write(path + "\n")
    return {"decision": "allow", "reason": "read recorded", "state_written": [str(reads)]}
