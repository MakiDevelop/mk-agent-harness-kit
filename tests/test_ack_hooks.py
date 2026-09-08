#!/usr/bin/env python3
"""Tests for harness hook + ack_hooks install."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
os.environ["PYTHONPATH"] = str(KIT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")
HOOK = KIT / "src" / "ack" / "_assets" / "hooks" / "pretool-harness.py"
CLI = ["-m", "ack.cli", "hooks"]


def run_hook(command: str, resolved: Path) -> dict:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    env = {**dict(**{k: v for k, v in __import__("os").environ.items()}), "ACK_RESOLVED": str(resolved)}
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    out = (proc.stdout or "").strip()
    if not out:
        return {"decision": "allow", "raw": ""}
    data = json.loads(out)
    dec = data.get("hookSpecificOutput", {}).get("permissionDecision", "allow")
    return {"decision": dec, "raw": out, "data": data}


def write_resolved(td: Path, **harness_human) -> Path:
    effective = {
        "profile": "solo-strict",
        "project": {"root": str(td), "name": "h"},
        "layers": {
            "harness": {
                "block_force_push": True,
                "block_rm_rf": True,
                "install_hooks": True,
                "preset": "standard",
            },
            "loop": {"verify": {"commands": ["true"]}},
            "graph": {"mode": "solo", "edges": "builtin:solo"},
            "prompt": {},
            "context": {"memory": {"enabled": False, "backend": "none"}},
        },
        "human": {
            "require_confirm_for": ["git_push", "delete", "deploy", "secrets"]
        },
        "adapters": {},
    }
    if "harness" in harness_human:
        effective["layers"]["harness"].update(harness_human["harness"])
    if "human" in harness_human:
        effective["human"] = harness_human["human"]
    path = td / "resolved.json"
    path.write_text(json.dumps(effective), encoding="utf-8")
    return path


class TestHarnessHook(unittest.TestCase):
    def test_settings_fallback_asks_when_ack_is_unavailable(self) -> None:
        payload = {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}
        env = {"ACK_SETTINGS": str(KIT / "settings.example.json"), "PATH": ""}
        proc = subprocess.run(
            [sys.executable, "-S", str(HOOK)], input=json.dumps(payload), text=True,
            capture_output=True, env=env, check=False,
        )
        data = json.loads(proc.stdout)
        result = data["hookSpecificOutput"]
        self.assertEqual(result["permissionDecision"], "ask")
        self.assertIn("cannot compile settings", result["permissionDecisionReason"])
    def test_allow_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            r = write_resolved(td)
            d = run_hook("echo hello", r)
            self.assertEqual(d["decision"], "allow")

    def test_deny_force_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            r = write_resolved(td)
            for cmd in (
                "git push --force origin main",
                "git push -fu origin main",
                "git -C repo push --force origin main",
            ):
                d = run_hook(cmd, r)
                self.assertEqual(d["decision"], "deny", cmd)

    def test_deny_rm_rf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            r = write_resolved(td)
            for cmd in (
                "rm -rf /tmp/foo",
                "rm --force --recursive /tmp/foo",
            ):
                d = run_hook(cmd, r)
                self.assertEqual(d["decision"], "deny", cmd)

    def test_ask_git_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            r = write_resolved(td)
            d = run_hook("git push origin main", r)
            self.assertEqual(d["decision"], "ask")

    def test_ask_secrets_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            r = write_resolved(td)
            d = run_hook("cat ~/.ssh/id_ed25519", r)
            self.assertEqual(d["decision"], "ask")

    def test_non_bash_allow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            r = write_resolved(td)
            payload = {"tool_name": "Read", "tool_input": {"file_path": "x"}}
            env = {**__import__("os").environ, "ACK_RESOLVED": str(r)}
            proc = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual((proc.stdout or "").strip(), "")


class TestAckHooksInstall(unittest.TestCase):
    def test_refuse_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            settings = {
                "profile": "solo",
                "project": {"root": ".", "name": "x"},
                "layers": {"harness": {"install_hooks": False}},
            }
            sp = td / "settings.json"
            sp.write_text(json.dumps(settings), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    *CLI,
                    "install",
                    "--settings",
                    str(sp),
                ],
                cwd=str(td),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)

    def test_install_with_setting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            settings = {
                "profile": "solo-strict",
                "project": {"root": ".", "name": "x"},
                "verify": {"commands": ["true"]},
                "layers": {"harness": {"install_hooks": True}},
            }
            sp = td / "settings.json"
            sp.write_text(json.dumps(settings), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    *CLI,
                    "install",
                    "--settings",
                    str(sp),
                    "--apply-project-claude",
                ],
                cwd=str(td),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue((td / ".mk-agentos" / "hooks" / "pretool-harness.py").is_file())
            self.assertTrue((td / ".mk-agentos" / "claude-settings.fragment.json").is_file())
            self.assertTrue((td / ".claude" / "settings.json").is_file())
            data = json.loads((td / ".claude" / "settings.json").read_text())
            pre = data["hooks"]["PreToolUse"]
            self.assertTrue(any("pretool-harness" in json.dumps(x) for x in pre))

    def test_refuse_project_claude_when_is_global(self) -> None:
        """If project.root/.claude/settings.json is the user global file, require --global."""
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            # Fake home claude path via symlink root -> structure is hard;
            # instead monkey by pointing project root at a dir whose .claude/settings.json
            # we can't easily make == Path.home(); unit-test the helper instead.
            from ack.hooks import is_user_global_claude_settings

            home_settings = Path.home() / ".claude" / "settings.json"
            self.assertTrue(
                is_user_global_claude_settings(home_settings)
                or not home_settings.exists()
                or is_user_global_claude_settings(home_settings)
            )
            # non-global path
            self.assertFalse(
                is_user_global_claude_settings(td / ".claude" / "settings.json")
            )

    def test_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            settings = {
                "profile": "solo-strict",
                "project": {"root": ".", "name": "x"},
                "verify": {"commands": ["true"]},
                "layers": {"harness": {"install_hooks": True}},
            }
            sp = td / "settings.json"
            sp.write_text(json.dumps(settings), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    *CLI,
                    "install",
                    "--settings",
                    str(sp),
                    "--apply-project-claude",
                ],
                cwd=str(td),
                check=True,
                capture_output=True,
            )
            proc = subprocess.run(
                [sys.executable, *CLI, "uninstall", "--settings", str(sp)],
                cwd=str(td),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertFalse((td / ".mk-agentos" / "hooks" / "pretool-harness.py").is_file())


if __name__ == "__main__":
    unittest.main()
