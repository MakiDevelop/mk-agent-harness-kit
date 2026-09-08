"""Portable project-state transition checks."""
from __future__ import annotations

import re
from typing import Any

from . import GuardContext
from ._projectstate import parse_text

TARGET = re.compile(r"/project-state\.(?:yaml|yml|json)$")

def _has(text: str, pattern: str, insensitive: bool = False) -> bool:
    return bool(re.search(pattern, text, re.I if insensitive else 0))

def run(payload: dict[str, Any], context: GuardContext) -> dict[str, Any]:
    data = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    path = data.get("file_path", data.get("path", "")); name = payload.get("tool_name", "")
    if not isinstance(path, str) or not TARGET.search(path): return {"decision": "noop", "reason": "not a project-state file"}
    if not __import__("pathlib").Path(path).is_file(): return {"decision": "noop", "reason": "new project-state file"}
    if name == "Edit":
        old, new = str(data.get("old_string", "")), str(data.get("new_string", ""))
        checks = [
            (r"status:\s*VERIFIED", r"verifier_id:\s*\S", "BLOCKED: Cannot push to VERIFIED without verifier_id (harness state-validator)", True),
            (r"status:\s*VERIFIED", r"evidence_id:\s*\S", "BLOCKED: Cannot push to VERIFIED without evidence_id (harness state-validator)", True),
            (r"status:\s*ACCEPTED", r"accepted_by:\s*\S", "BLOCKED: Cannot push to ACCEPTED without accepted_by (harness state-validator)", True),
            (r"tech_verified:\s*true", r"evidence_id:\s*\S", "BLOCKED: Cannot set tech_verified: true without evidence_id (harness state-validator)", False),
            (r"business_aligned:\s*true", r"aligned_by:\s*\S", "BLOCKED: Cannot set business_aligned: true without aligned_by (harness state-validator)", False),
        ]
        for trigger, required, reason, insensitive in checks:
            if _has(new, trigger, insensitive) and not _has(old, trigger, insensitive) and not _has(new, required): return {"decision": "deny", "reason": reason}
        return {"decision": "allow", "reason": "state transition valid"}
    if name != "Write" or not data.get("content"): return {"decision": "allow", "reason": "state validator not applicable"}
    try: parsed = parse_text(str(data["content"]))
    except (ValueError, TypeError, __import__("json").JSONDecodeError): return {"decision": "allow", "reason": "project-state unparsable, validator skipped"}
    errors: list[str] = []
    for task in parsed.get("tasks", []):
        if not isinstance(task, dict): continue
        status, tid = str(task.get("status", "")), str(task.get("id", "?"))
        if status == "VERIFIED":
            if not task.get("verifier_id"): errors.append(f"Task {tid}: VERIFIED requires verifier_id")
            criteria = task.get("acceptance_criteria", []); criterion_evidence = any(isinstance(x, dict) and x.get("evidence_id") for x in criteria) if isinstance(criteria, list) else False
            if not task.get("evidence_id") and not criterion_evidence: errors.append(f"Task {tid}: VERIFIED requires evidence_id")
            if str(task.get("tech_verified", "")).lower() != "true": errors.append(f"Task {tid}: VERIFIED requires tech_verified: true")
            if str(task.get("business_aligned", "")).lower() != "true": errors.append(f"Task {tid}: VERIFIED requires business_aligned: true")
        if status == "ACCEPTED" and not task.get("accepted_by"): errors.append(f"Task {tid}: ACCEPTED requires accepted_by")
    if errors: return {"decision": "deny", "reason": "BLOCKED by harness state-validator: " + "; ".join(errors)}
    return {"decision": "allow", "reason": "project-state valid"}
