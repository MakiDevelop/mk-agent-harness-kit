#!/usr/bin/env python3
"""ack_loop — enforce loop policy from effective settings.

Agents must call `verify` / `done-gate` before claiming done.
On wall (max consecutive verify failures), emit system-gap and exit 2.

No network. No home-lab assumptions.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Import sibling module without install
_CLI_DIR = Path(__file__).resolve().parent
if str(_CLI_DIR) not in sys.path:
    sys.path.insert(0, str(_CLI_DIR))

import ack_settings  # noqa: E402

STATE_DIRNAME = ".mk-agentos"
STATE_FILENAME = "loop-state.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_effective(settings_path: Path | None, resolved_path: Path | None) -> dict[str, Any]:
    if resolved_path is not None:
        data = json.loads(resolved_path.read_text(encoding="utf-8"))
        if "layers" not in data:
            raise SystemExit(f"resolved file missing layers: {resolved_path}")
        return data
    if settings_path is None:
        raise SystemExit("need --settings or --resolved")
    raw = ack_settings.load_json(settings_path)
    schema = Path(
        os.environ.get("ACK_SETTINGS_SCHEMA", str(ack_settings.DEFAULT_SCHEMA))
    )
    errors = ack_settings.schema_validate(raw, schema)
    if errors:
        print("SCHEMA FAIL", file=sys.stderr)
        for e in errors:
            print(" ", e, file=sys.stderr)
        raise SystemExit(1)
    try:
        return ack_settings.compile_settings(raw)
    except ValueError as exc:
        print("COMPILE INVARIANT FAIL:", exc, file=sys.stderr)
        raise SystemExit(1) from exc


def project_root(effective: dict[str, Any], cwd: Path) -> Path:
    root = (effective.get("project") or {}).get("root") or "."
    p = Path(root)
    if not p.is_absolute():
        p = (cwd / p).resolve()
    return p


def state_path(root: Path) -> Path:
    return root / STATE_DIRNAME / STATE_FILENAME


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "consecutive_verify_failures": 0,
            "wall_hit": False,
            "last_verify": None,
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "consecutive_verify_failures": 0,
            "wall_hit": False,
            "last_verify": None,
            "corrupt_previous": True,
        }


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def loop_policy(effective: dict[str, Any]) -> dict[str, Any]:
    return (effective.get("layers") or {}).get("loop") or {}


def verify_commands(effective: dict[str, Any]) -> list[str]:
    loop = loop_policy(effective)
    cmds = (loop.get("verify") or {}).get("commands") or []
    return [c for c in cmds if isinstance(c, str) and c.strip()]


def run_verify_commands(
    commands: list[str], cwd: Path
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                check=False,
            )
            results.append(
                {
                    "command": cmd,
                    "exit_code": proc.returncode,
                    "ok": proc.returncode == 0,
                    "stdout_tail": (proc.stdout or "")[-2000:],
                    "stderr_tail": (proc.stderr or "")[-2000:],
                }
            )
        except OSError as exc:
            results.append(
                {
                    "command": cmd,
                    "exit_code": 127,
                    "ok": False,
                    "stdout_tail": "",
                    "stderr_tail": str(exc),
                }
            )
    return results


def format_system_gap(
    *,
    mode: str,
    control: str = "hook|docs|skill|edge-contract|graph",
    ratify: str = "no",
) -> str:
    return f"{{error_mode: {mode}}} → {{control: {control}}} → {{ratify?: {ratify}}}"


def emit_wall_gaps(effective: dict[str, Any], state: dict[str, Any]) -> list[str]:
    loop = loop_policy(effective)
    gaps: list[str] = []
    if loop.get("require_system_gap_on_wall", True) and state.get("wall_hit"):
        gaps.append(
            format_system_gap(
                mode="verify failed max_failed_attempts times (wall)",
                control="loop.verify.commands|skill",
                ratify="no",
            )
        )
    if not gaps and state.get("wall_hit"):
        gaps.append("system-gap: wall_hit (require_system_gap_on_wall=false)")
    return gaps


def cmd_verify(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    root = project_root(effective, cwd)
    loop = loop_policy(effective)
    max_fail = int(loop.get("max_failed_attempts") or 2)
    commands = verify_commands(effective)

    sp = state_path(root)
    state = load_state(sp)

    if not commands:
        print("VERIFY SKIP: no loop.verify.commands configured")
        print("done-gate: cannot claim done without verify commands (solo may add them)")
        state["last_verify"] = {
            "ok": False,
            "skipped": True,
            "at": _utc_now(),
            "reason": "empty_commands",
        }
        # empty commands: not a success for done-gate semantics when profile is strict
        # For solo with empty list, verify exits 3 = incomplete policy
        save_state(sp, state)
        return 3

    print(f"project_root: {root}")
    print(f"running {len(commands)} verify command(s)…")
    results = run_verify_commands(commands, root)
    all_ok = all(r["ok"] for r in results)

    for r in results:
        status = "OK" if r["ok"] else "FAIL"
        print(f"  [{status}] exit={r['exit_code']}  {r['command']}")
        if not r["ok"] and r.get("stderr_tail"):
            err = r["stderr_tail"].strip().splitlines()
            for line in err[-5:]:
                print(f"    stderr: {line}")

    state["last_verify"] = {
        "ok": all_ok,
        "at": _utc_now(),
        "results": [
            {"command": r["command"], "exit_code": r["exit_code"], "ok": r["ok"]}
            for r in results
        ],
    }

    if all_ok:
        state["consecutive_verify_failures"] = 0
        state["wall_hit"] = False
        save_state(sp, state)
        print("VERIFY PASS")
        print("done-gate: OPEN (verify green)")
        return 0

    fails = int(state.get("consecutive_verify_failures") or 0) + 1
    state["consecutive_verify_failures"] = fails
    if fails >= max_fail:
        state["wall_hit"] = True
        save_state(sp, state)
        print(f"VERIFY FAIL ({fails}/{max_fail}) — WALL")
        print("done-gate: CLOSED")
        for g in emit_wall_gaps(effective, state):
            print("SYSTEM_GAP:", g)
        print(
            "Agent must STOP code changes, report system-gap, and not claim done."
        )
        return 2

    save_state(sp, state)
    print(f"VERIFY FAIL ({fails}/{max_fail})")
    print("done-gate: CLOSED (fix then re-run verify)")
    return 1


def cmd_status(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    root = project_root(effective, cwd)
    loop = loop_policy(effective)
    sp = state_path(root)
    state = load_state(sp)
    max_fail = int(loop.get("max_failed_attempts") or 2)
    print(f"project_root: {root}")
    print(f"state_file: {sp}")
    print(f"consecutive_verify_failures: {state.get('consecutive_verify_failures', 0)}/{max_fail}")
    print(f"wall_hit: {bool(state.get('wall_hit'))}")
    print(f"last_verify: {json.dumps(state.get('last_verify'), ensure_ascii=False)}")
    print(f"verify.commands: {verify_commands(effective)}")
    print(
        f"require_system_gap_on_wall: {loop.get('require_system_gap_on_wall', True)}"
    )
    print(
        f"require_system_gap_on_wrap: {loop.get('require_system_gap_on_wrap', True)}"
    )
    if state.get("wall_hit"):
        for g in emit_wall_gaps(effective, state):
            print("SYSTEM_GAP:", g)
    return 0


def cmd_wrap_gap(args: argparse.Namespace) -> int:
    """Emit system-gap lines for wrap-up: always `system-gap: none` or concrete gaps."""
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    root = project_root(effective, cwd)
    loop = loop_policy(effective)
    state = load_state(state_path(root))
    require_wrap = bool(loop.get("require_system_gap_on_wrap", True))

    gaps: list[str] = []
    if state.get("wall_hit") and loop.get("require_system_gap_on_wall", True):
        gaps.extend(emit_wall_gaps(effective, state))

    last = state.get("last_verify") or {}
    if last.get("ok") is False and not last.get("skipped") and not state.get("wall_hit"):
        gaps.append(
            format_system_gap(
                mode="last verify failed (not yet wall)",
                control="loop.verify.commands",
                ratify="no",
            )
        )

    # empty policy: still a concrete gap so wrap contract stays binary (none | gaps)
    if last.get("skipped") or (
        require_wrap and not verify_commands(effective) and not last.get("ok")
    ):
        gaps.append(
            format_system_gap(
                mode="loop.verify.commands empty (cannot prove done)",
                control="settings.verify.commands",
                ratify="no",
            )
        )

    # de-dupe while preserving order
    seen: set[str] = set()
    uniq_gaps: list[str] = []
    for g in gaps:
        if g not in seen:
            seen.add(g)
            uniq_gaps.append(g)

    if not uniq_gaps:
        print("system-gap: none")
        return 0

    for g in uniq_gaps:
        if g.startswith("system-gap:"):
            print(g)
        else:
            print("SYSTEM_GAP:", g)
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    root = project_root(effective, cwd)
    sp = state_path(root)
    state = {
        "consecutive_verify_failures": 0,
        "wall_hit": False,
        "last_verify": None,
        "reset_at": _utc_now(),
    }
    save_state(sp, state)
    print("loop state reset:", sp)
    return 0


def _add_settings_args(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--settings", help="raw settings.json (will compile)")
    g.add_argument("--resolved", help="precompiled settings.resolved.json")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ack_loop",
        description="Enforce loop verify / wall / system-gap from effective settings",
    )
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser(
        "verify",
        help="run verify.commands; update wall counter; gate done",
    )
    _add_settings_args(v)
    v.set_defaults(func=cmd_verify)

    # alias
    d = sub.add_parser(
        "done-gate",
        help="same as verify — call before claiming task done",
    )
    _add_settings_args(d)
    d.set_defaults(func=cmd_verify)

    s = sub.add_parser("status", help="show loop state and policy")
    _add_settings_args(s)
    s.set_defaults(func=cmd_status)

    w = sub.add_parser("wrap-gap", help="print system-gap lines for wrap-up")
    _add_settings_args(w)
    w.set_defaults(func=cmd_wrap_gap)

    r = sub.add_parser("reset", help="clear consecutive failure / wall state")
    _add_settings_args(r)
    r.set_defaults(func=cmd_reset)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
