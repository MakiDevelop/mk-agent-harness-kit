"""Stateful Claude Code hook guards with a common JSON envelope."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any

Guard = Callable[[dict[str, Any], "GuardContext"], dict[str, Any]]


class GuardContext:
    def __init__(self, project_root, evidence_dir) -> None:  # type: ignore[no-untyped-def]
        self.project_root = project_root
        self.evidence_dir = evidence_dir


from . import council_dispatch_guard, evidence, first_read_lock, preset_auto_upgrade, read_tracker, session_onboarding


def _noop(_: dict[str, Any], __: GuardContext) -> dict[str, Any]:
    return {"decision": "noop", "reason": "not implemented in this release"}


GUARDS: dict[str, Guard] = {
    "read-tracker": read_tracker.run,
    "evidence": evidence.run,
    "first-read-lock": first_read_lock.run,
    "council-dispatch-guard": council_dispatch_guard.run,
    "no-progress-guard": _noop,
    "preset-auto-upgrade": preset_auto_upgrade.run,
    "progress-tracker": _noop,
    "session-onboarding": session_onboarding.run,
    "state-validator": _noop,
}


def _envelope(name: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "guard": name,
        "decision": result["decision"],
        "reason": result["reason"],
        "context": result.get("context"),
        "state_written": result.get("state_written", []),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ack guard")
    p.add_argument("name", choices=GUARDS)
    p.add_argument("--settings")
    p.add_argument("--project-root")
    p.add_argument("--stdin-json", action="store_true")
    p.add_argument("--verify", action="store_true", help="verify the evidence vault chain")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.verify:
        if args.name != "evidence":
            print("error: --verify is only valid for evidence", file=sys.stderr)
            return 2
        try:
            context = evidence.context_from_args(args.project_root, args.settings)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return evidence.verify(context.evidence_dir / "vault.jsonl")
    if not args.stdin_json:
        print("error: --stdin-json is required", file=sys.stderr)
        return 2
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("stdin JSON must be an object")
        context = evidence.context_from_args(args.project_root, args.settings)
        result = GUARDS[args.name](payload, context)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(_envelope(args.name, result), ensure_ascii=False, separators=(",", ":")))
    return 0
