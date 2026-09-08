"""Legacy-compatible, intentionally shallow Council CLI command guard."""
from __future__ import annotations

import re
from typing import Any

from . import GuardContext

_SEGMENTS = re.compile(r"\|\||&&|[;&|()`]")
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
_WRAPPERS = frozenset({"timeout", "env", "nice", "nohup", "stdbuf", "command", "exec", "xargs"})
_GEMINI_FLAGS = frozenset({"-p", "-i", "--print", "--prompt", "--prompt-interactive"})


def _settings(context: GuardContext) -> tuple[str, dict[str, list[str]]]:
    settings = getattr(context, "settings", {})
    council = settings.get("layers", {}).get("harness", {}).get("council", {}) if isinstance(settings, dict) else {}
    dispatcher = council.get("dispatcher", "council-dispatch") if isinstance(council, dict) else "council-dispatch"
    blocked = council.get("blocked_clis", {}) if isinstance(council, dict) else {}
    defaults = {"codex": ["exec"], **{name: sorted(_GEMINI_FLAGS) for name in ("gemini", "grok", "agy")}}
    if isinstance(blocked, dict):
        for name, flags in blocked.items():
            if isinstance(name, str) and isinstance(flags, list) and all(isinstance(x, str) for x in flags):
                defaults[name] = flags
    return dispatcher if isinstance(dispatcher, str) else "council-dispatch", defaults


def _strip(segment: str) -> list[str]:
    tokens = segment.split()
    while len(tokens) > 1:
        first = tokens[0]
        # Legacy parity: the shell `case` used `[0-9]*)`, i.e. any token that
        # *starts* with a digit (e.g. `timeout 30s`), not only pure integers.
        if _ASSIGNMENT.fullmatch(first) or first in _WRAPPERS or first.startswith("-") or first[0].isdigit():
            tokens.pop(0)
        else:
            break
    return tokens


def run(payload: dict[str, Any], context: GuardContext) -> dict[str, Any]:
    if payload.get("tool_name") != "Bash":
        return {"decision": "noop", "reason": "not a Bash tool"}
    source = payload.get("tool_input")
    command = source.get("command", "") if isinstance(source, dict) else ""
    if not isinstance(command, str) or not command:
        return {"decision": "noop", "reason": "no Bash command"}
    dispatcher, blocked = _settings(context)
    if dispatcher in command:
        return {"decision": "allow", "reason": "approved council dispatcher"}
    for segment in _SEGMENTS.split(command):
        tokens = _strip(segment)
        if not tokens:
            continue
        binary = tokens[0].rsplit("/", 1)[-1]
        flags = blocked.get(binary, [])
        if binary == "codex" and "exec" in flags and "exec" in tokens[1:]:
            return {"decision": "deny", "reason": "Direct Council CLI dispatch is not allowed (codex exec). Use council-dispatch."}
        if binary in blocked and binary != "codex":
            # Any CLI listed in layers.harness.council.blocked_clis (defaults
            # cover gemini / grok / agy) — custom entries must be honoured too.
            for token in tokens[1:]:
                if token in flags or any(token.startswith(flag + "=") for flag in flags):
                    return {"decision": "deny", "reason": f"Direct Council CLI dispatch is not allowed ({binary}). Use council-dispatch."}
    return {"decision": "allow", "reason": "no direct council dispatch"}
