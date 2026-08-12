#!/usr/bin/env python3
"""ack_hooks — opt-in install of portable harness PreToolUse hooks.

Never writes to ~/.claude unless --global is passed (still requires install_hooks
or --i-understand).

Default install target: {project.root}/.mk-agentos/ + optional project .claude/settings.json
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

_CLI = Path(__file__).resolve().parent
KIT = _CLI.parent
HOOK_SRC = KIT / "hooks" / "pretool-harness.py"

if str(_CLI) not in sys.path:
    sys.path.insert(0, str(_CLI))

import ack_settings  # noqa: E402


def load_effective(settings: Path | None, resolved: Path | None) -> dict[str, Any]:
    if resolved:
        return json.loads(Path(resolved).read_text(encoding="utf-8"))
    if not settings:
        raise SystemExit("need --settings or --resolved")
    raw = ack_settings.load_json(Path(settings))
    schema = Path(os.environ.get("ACK_SETTINGS_SCHEMA", str(ack_settings.DEFAULT_SCHEMA)))
    errs = ack_settings.schema_validate(raw, schema)
    if errs:
        print("SCHEMA FAIL", file=sys.stderr)
        for e in errs:
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


def install_allowed(effective: dict[str, Any], i_understand: bool) -> bool:
    h = (effective.get("layers") or {}).get("harness") or {}
    if h.get("install_hooks") is True:
        return True
    return i_understand


def hook_command(hook_path: Path, resolved_path: Path) -> str:
    # Absolute paths so Claude can run from any cwd; quote for spaces/meta
    return (
        f"ACK_RESOLVED={shlex.quote(str(resolved_path))} "
        f"{shlex.quote(sys.executable)} {shlex.quote(str(hook_path))}"
    )


def is_user_global_claude_settings(path: Path) -> bool:
    try:
        target = path.resolve()
        home = (Path.home() / ".claude" / "settings.json").resolve()
        return target == home
    except OSError:
        return False


def claude_fragment(hook_cmd: str) -> dict[str, Any]:
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": hook_cmd,
                        }
                    ],
                }
            ]
        }
    }


def merge_claude_settings(target: Path, fragment: dict[str, Any]) -> None:
    existing: dict[str, Any] = {}
    if target.is_file():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSON: {target}: {exc}") from exc

    hooks = existing.setdefault("hooks", {})
    pre = hooks.setdefault("PreToolUse", [])
    if not isinstance(pre, list):
        raise SystemExit(f"hooks.PreToolUse must be a list in {target}")

    cmd = fragment["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    # remove previous ack harness entries
    new_pre = []
    for item in pre:
        try:
            inner = item.get("hooks") or []
            cmds = " ".join(h.get("command", "") for h in inner)
            if "pretool-harness.py" in cmds or "agent-contract-kit/hooks" in cmds:
                continue
        except Exception:
            pass
        new_pre.append(item)
    new_pre.append(fragment["hooks"]["PreToolUse"][0])
    hooks["PreToolUse"] = new_pre
    existing["hooks"] = hooks
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_install(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    if not install_allowed(effective, args.i_understand):
        print(
            "REFUSED: harness.install_hooks is false.\n"
            "Set layers.harness.install_hooks=true in settings.json, or pass --i-understand.\n"
            "Silent global install is never performed.",
            file=sys.stderr,
        )
        return 2

    if not HOOK_SRC.is_file():
        print("missing hook source:", HOOK_SRC, file=sys.stderr)
        return 1

    root = project_root(effective, cwd)
    mk = root / ".mk-agentos"
    hooks_dir = mk / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    dest_hook = hooks_dir / "pretool-harness.py"
    shutil.copy2(HOOK_SRC, dest_hook)
    dest_hook.chmod(dest_hook.stat().st_mode | 0o111)

    # ensure resolved snapshot next to hooks
    resolved_path = mk / "settings.resolved.json"
    if args.settings:
        raw = ack_settings.load_json(Path(args.settings))
        resolved = ack_settings.compile_settings(raw)
        # force install_hooks true in snapshot if user used --i-understand
        if args.i_understand:
            resolved.setdefault("layers", {}).setdefault("harness", {})[
                "install_hooks"
            ] = True
        resolved_path.write_text(
            json.dumps(resolved, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    elif args.resolved:
        shutil.copy2(Path(args.resolved), resolved_path)
    elif not resolved_path.is_file():
        resolved_path.write_text(
            json.dumps(effective, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    hook_cmd = hook_command(dest_hook.resolve(), resolved_path.resolve())
    fragment = claude_fragment(hook_cmd)
    frag_path = mk / "claude-settings.fragment.json"
    frag_path.write_text(json.dumps(fragment, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("installed hook:", dest_hook)
    print("resolved:", resolved_path)
    print("fragment:", frag_path)

    if args.apply_project_claude:
        target = root / ".claude" / "settings.json"
        if is_user_global_claude_settings(target):
            print(
                "REFUSED: project root resolves to user global ~/.claude/settings.json.\n"
                "Use --global --i-understand explicitly instead of --apply-project-claude.",
                file=sys.stderr,
            )
            return 2
        merge_claude_settings(target, fragment)
        print("merged into", target)

    if args.global_claude:
        target = Path.home() / ".claude" / "settings.json"
        if not args.i_understand:
            print("REFUSED: --global requires --i-understand", file=sys.stderr)
            return 2
        merge_claude_settings(target, fragment)
        # record marker for uninstall
        marker = mk / "global_install_marker.json"
        marker.write_text(
            json.dumps({"target": str(target.resolve())}, indent=2) + "\n",
            encoding="utf-8",
        )
        print("merged into", target)
        print("WARNING: modified user global Claude settings")

    if not args.apply_project_claude and not args.global_claude:
        print(
            "\nNext: merge fragment into Claude Code settings, or re-run with "
            "--apply-project-claude to write {project}/.claude/settings.json"
        )
    return 0


def _clean_pretool_entries(target: Path) -> bool:
    if not target.is_file():
        return False
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    pre = (data.get("hooks") or {}).get("PreToolUse") or []
    if not isinstance(pre, list):
        return False
    new_pre = []
    changed = False
    for item in pre:
        try:
            cmds = " ".join(h.get("command", "") for h in (item.get("hooks") or []))
            if "pretool-harness.py" in cmds:
                changed = True
                continue
        except Exception:
            pass
        new_pre.append(item)
    if not changed:
        return False
    data.setdefault("hooks", {})["PreToolUse"] = new_pre
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("cleaned", target)
    return True


def cmd_uninstall(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    root = project_root(effective, cwd)
    mk = root / ".mk-agentos"
    hook = mk / "hooks" / "pretool-harness.py"
    frag = mk / "claude-settings.fragment.json"
    for p in (hook, frag):
        if p.is_file():
            p.unlink()
            print("removed", p)

    _clean_pretool_entries(root / ".claude" / "settings.json")

    marker = mk / "global_install_marker.json"
    if args.global_claude or marker.is_file():
        if args.global_claude and not args.i_understand:
            print("REFUSED: cleaning global settings requires --i-understand", file=sys.stderr)
            return 2
        global_target = Path.home() / ".claude" / "settings.json"
        if marker.is_file():
            try:
                meta = json.loads(marker.read_text(encoding="utf-8"))
                global_target = Path(meta.get("target") or global_target)
            except json.JSONDecodeError:
                pass
            marker.unlink()
            print("removed", marker)
        _clean_pretool_entries(global_target)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    effective = load_effective(
        Path(args.settings) if args.settings else None,
        Path(args.resolved) if args.resolved else None,
    )
    root = project_root(effective, cwd)
    h = (effective.get("layers") or {}).get("harness") or {}
    print(f"project_root: {root}")
    print(f"install_hooks setting: {h.get('install_hooks')}")
    print(f"block_force_push: {h.get('block_force_push')}")
    print(f"block_rm_rf: {h.get('block_rm_rf')}")
    print(f"require_confirm_for: {(effective.get('human') or {}).get('require_confirm_for')}")
    hook = root / ".mk-agentos" / "hooks" / "pretool-harness.py"
    print(f"hook_installed: {hook.is_file()} ({hook})")
    frag = root / ".mk-agentos" / "claude-settings.fragment.json"
    print(f"fragment: {frag.is_file()} ({frag})")
    return 0


def cmd_test_cmd(args: argparse.Namespace) -> int:
    """Run harness against a shell command string (no Claude). Exit 0 always;
    print decision on stdout for tests."""
    # Simulate stdin JSON
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": args.command},
    }
    env = os.environ.copy()
    if args.resolved:
        env["ACK_RESOLVED"] = str(Path(args.resolved).resolve())
    elif args.settings:
        # compile to temp resolved via import
        effective = load_effective(Path(args.settings), None)
        # write temp under .mk-agentos if possible
        root = project_root(effective, Path.cwd())
        mk = root / ".mk-agentos"
        mk.mkdir(parents=True, exist_ok=True)
        resolved = mk / "settings.resolved.json"
        resolved.write_text(json.dumps(effective, indent=2) + "\n", encoding="utf-8")
        env["ACK_RESOLVED"] = str(resolved.resolve())

    import subprocess

    proc = subprocess.run(
        [sys.executable, str(HOOK_SRC)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    out = (proc.stdout or "").strip()
    if out:
        print(out)
        try:
            data = json.loads(out)
            dec = (
                data.get("hookSpecificOutput", {}).get("permissionDecision")
                or "allow"
            )
            print("decision:", dec, file=sys.stderr)
            return 0 if dec in ("deny", "ask", "allow") else 0
        except json.JSONDecodeError:
            pass
    else:
        print("{}", end="")
        print("decision: allow", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ack_hooks", description="Install portable harness hooks")
    sub = p.add_subparsers(dest="command", required=True)

    def add_src(sp: argparse.ArgumentParser) -> None:
        g = sp.add_mutually_exclusive_group(required=True)
        g.add_argument("--settings")
        g.add_argument("--resolved")

    inst = sub.add_parser("install", help="copy hook + write fragment (opt-in)")
    add_src(inst)
    inst.add_argument(
        "--i-understand",
        action="store_true",
        help="allow install even if install_hooks is false; required for --global",
    )
    inst.add_argument(
        "--apply-project-claude",
        action="store_true",
        help="merge fragment into {project}/.claude/settings.json",
    )
    inst.add_argument(
        "--global",
        dest="global_claude",
        action="store_true",
        help="merge into ~/.claude/settings.json (requires --i-understand)",
    )
    inst.set_defaults(func=cmd_install)

    un = sub.add_parser("uninstall", help="remove project hook + clean settings entries")
    add_src(un)
    un.add_argument(
        "--global",
        dest="global_claude",
        action="store_true",
        help="also clean ~/.claude/settings.json (requires --i-understand)",
    )
    un.add_argument(
        "--i-understand",
        action="store_true",
        help="required with --global uninstall",
    )
    un.set_defaults(func=cmd_uninstall)

    st = sub.add_parser("status", help="show harness install state")
    add_src(st)
    st.set_defaults(func=cmd_status)

    t = sub.add_parser("test-cmd", help="run harness against a command string")
    add_src(t)
    t.add_argument("--command", required=True)
    t.set_defaults(func=cmd_test_cmd)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
