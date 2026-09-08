#!/usr/bin/env python3
"""Portable PreToolUse harness guard (Claude Code / compatible JSON stdin).

Reads effective settings from:
  1) env ACK_RESOLVED (path to settings.resolved.json)
  2) env ACK_SETTINGS (path to settings.json — compiled in-process)
  3) ./{project}/.mk-agentos/settings.resolved.json walking up from cwd
  4) safe defaults if missing (block force push + rm -rf)

Deny protocol (Claude Code):
  exit 0 + stdout JSON hookSpecificOutput.permissionDecision = deny|ask

No network. No home-lab paths required.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _deny(reason: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"🚫 HARNESS: {reason}",
        }
    }
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


def _ask(reason: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"⚠️ HARNESS confirm: {reason}",
        }
    }
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


def _allow() -> None:
    sys.exit(0)


def find_resolved() -> Path | None:
    env = os.environ.get("ACK_RESOLVED") or os.environ.get("ACK_SETTINGS_RESOLVED")
    if env:
        p = Path(env)
        if p.is_file():
            return p
    cwd = Path.cwd().resolve()
    for base in [cwd, *cwd.parents]:
        cand = base / ".mk-agentos" / "settings.resolved.json"
        if cand.is_file():
            return cand
        # stop at filesystem root naturally
        if base == base.parent:
            break
    return None


def compile_settings(path: Path) -> dict[str, Any]:
    """Compile settings using the package, or the installed ``ack`` command."""
    try:
        from ack import settings as ack_settings

        return ack_settings.compile_settings(ack_settings.load_json(path))
    except Exception as import_error:
        ack_bin = shutil.which("ack") or "ack"
        try:
            proc = subprocess.run(
                [ack_bin, "settings", "compile", "--settings", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "ack settings compile failed").strip()
                raise RuntimeError(f"cannot compile settings: {detail}") from import_error
            return json.loads(proc.stdout)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"cannot compile settings: {exc}") from import_error


def load_effective() -> dict[str, Any]:
    resolved = find_resolved()
    if resolved is not None:
        try:
            return json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    settings_env = os.environ.get("ACK_SETTINGS")
    if settings_env and Path(settings_env).is_file():
        return compile_settings(Path(settings_env))

    # Safe defaults when no settings (fail closed on worst ops only)
    return {
        "layers": {
            "harness": {
                "block_force_push": True,
                "block_rm_rf": True,
                "install_hooks": False,
            }
        },
        "human": {
            "require_confirm_for": [
                "git_push",
                "delete",
                "deploy",
                "secrets",
            ]
        },
    }


def harness_flags(effective: dict[str, Any]) -> dict[str, Any]:
    return (effective.get("layers") or {}).get("harness") or {}


def confirm_for(effective: dict[str, Any]) -> set[str]:
    human = effective.get("human") or {}
    items = human.get("require_confirm_for") or []
    return set(items) | {"secrets"}  # always secrets


# Patterns — intentional heuristics for shell command strings (not a shell AST)
# Detect git … push with force flags even when -C / combined shorts intervene.
FORCE_PUSH = re.compile(
    r"\bgit\b[\s\S]{0,200}?\bpush\b[\s\S]{0,120}?(--force-with-lease|--force\b|-\w*f\w*)",
    re.I,
)
FORCE_PLUS = re.compile(r"\bgit\b[\s\S]{0,200}?\bpush\b[\s\S]{0,80}?\s\+[A-Za-z0-9._/-]+", re.I)
RESET_HARD = re.compile(r"\bgit\b[\s\S]{0,80}?\breset\b[\s\S]{0,40}?--hard\b", re.I)
CLEAN_FORCE = re.compile(r"\bgit\b[\s\S]{0,80}?\bclean\b[\s\S]{0,40}?-f", re.I)
RM_RF = re.compile(
    r"\brm\b[\s\S]{0,80}?(--recursive[\s\S]{0,40}--force|--force[\s\S]{0,40}--recursive)",
    re.I,
)
RM_RF_SIMPLE = re.compile(r"\brm\s+(-[^\s]*r[^\s]*f[^\s]*|-[^\s]*f[^\s]*r[^\s]*)\b", re.I)
GIT_PUSH = re.compile(r"\bgit\b[\s\S]{0,200}?\bpush\b", re.I)
DEPLOY = re.compile(
    r"\b(kubectl\s+apply|helm\s+upgrade|terraform\s+apply|gcloud\s+run\s+deploy|firebase\s+deploy|wrangler\s+deploy|docker\s+stack\s+deploy)\b",
    re.I,
)
SECRETS_PATH = re.compile(
    r"(^|[\s'\"])/?(Users|home)/[^\s'\"]*/\.(ssh|gnupg|aws|secrets)(/|\s|$)|"
    r"(^|[\s'\"])~/\.(ssh|gnupg|aws|secrets)\b|"
    r"\.env\b|id_rsa|id_ed25519|credentials\.json",
    re.I,
)
DROP_DB = re.compile(r"\b(DROP\s+(DATABASE|TABLE)|TRUNCATE\s+TABLE)\b", re.I)


def check_bash(command: str, effective: dict[str, Any]) -> None:
    h = harness_flags(effective)
    confirms = confirm_for(effective)

    if h.get("block_force_push", True):
        if FORCE_PUSH.search(command) or FORCE_PLUS.search(command):
            _deny("git force push blocked (harness.block_force_push)")
        if RESET_HARD.search(command):
            _deny("git reset --hard blocked (destructive git)")
        if CLEAN_FORCE.search(command):
            _deny("git clean -f blocked (destructive git)")

    if h.get("block_rm_rf", True):
        if RM_RF_SIMPLE.search(command) or RM_RF.search(command):
            _deny("rm -rf / recursive force remove blocked (harness.block_rm_rf)")

    if DROP_DB.search(command):
        _deny("DROP/TRUNCATE database/table blocked")

    # confirm-style (ask) for configured categories
    if "git_push" in confirms and GIT_PUSH.search(command):
        if not (FORCE_PUSH.search(command) or FORCE_PLUS.search(command)):
            _ask("git push requires human confirmation (human.require_confirm_for)")

    if "git_force_push" in confirms and (
        FORCE_PUSH.search(command) or FORCE_PLUS.search(command)
    ):
        # already denied if block_force_push; if disabled, ask
        if not h.get("block_force_push", True):
            _ask("force push requires confirmation")

    if "deploy" in confirms and DEPLOY.search(command):
        _ask("deploy-like command requires human confirmation")

    if "delete" in confirms and re.search(r"\b(rm\s+|unlink\s+|shred\s+)", command):
        # non -rf deletes still ask when delete is in confirm list
        if not (RM_RF_SIMPLE.search(command) or RM_RF.search(command)):
            _ask("delete/remove requires human confirmation")

    if "secrets" in confirms and SECRETS_PATH.search(command):
        _ask("command touches secret-like paths; confirm required")

    if "governance_edit" in confirms and re.search(
        r"(CLAUDE\.md|settings\.json|AGENTS\.md|OPEN-LOOPS|\.claude/|/hooks/)",
        command,
        re.I,
    ):
        if re.search(r"\b(rm|mv|sed|tee|>\s*|>>)\b", command):
            _ask("possible governance file edit; confirm required")


def main() -> None:
    try:
        raw = sys.stdin.read()
    except OSError:
        _allow()

    if not raw.strip():
        _allow()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Non-JSON callers: treat whole stdin as command string for tests
        data = {"tool_name": "Bash", "tool_input": {"command": raw.strip()}}

    tool = data.get("tool_name") or data.get("tool") or ""
    # Only Bash for M3; other tools pass
    if tool and tool not in ("Bash", "bash", "Shell", "shell"):
        _allow()

    command = ""
    tin = data.get("tool_input") or data.get("input") or {}
    if isinstance(tin, dict):
        command = tin.get("command") or tin.get("cmd") or ""
    if not command and isinstance(data.get("command"), str):
        command = data["command"]

    if not command:
        _allow()

    try:
        effective = load_effective()
    except RuntimeError as exc:
        _ask(str(exc))
    check_bash(command, effective)
    _allow()


if __name__ == "__main__":
    main()
