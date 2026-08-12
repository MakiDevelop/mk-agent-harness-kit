#!/usr/bin/env python3
"""Tests for cli/ack_loop.py"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
CLI = KIT / "cli" / "ack_loop.py"
SETTINGS_CLI = KIT / "cli" / "ack_settings.py"
ROOT = KIT.parents[1]


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


class TestAckLoop(unittest.TestCase):
    def _write_settings(self, td: Path, commands: list[str], profile: str = "solo-strict") -> Path:
        settings = {
            "profile": profile,
            "project": {"root": ".", "name": "loop-test"},
            "verify": {"commands": commands},
        }
        if profile in ("dual-review", "governed"):
            settings["layers"] = {
                "graph": {
                    "agents": {"executor": "a", "reviewer": "b"},
                }
            }
        path = td / "settings.json"
        path.write_text(json.dumps(settings), encoding="utf-8")
        return path

    def test_verify_pass_resets_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            settings = self._write_settings(td, [f"{sys.executable} -c \"raise SystemExit(0)\""])
            r1 = run_cli(["verify", "--settings", str(settings)], td)
            self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
            self.assertIn("VERIFY PASS", r1.stdout)
            state = json.loads((td / ".mk-agentos" / "loop-state.json").read_text())
            self.assertEqual(state["consecutive_verify_failures"], 0)
            self.assertFalse(state["wall_hit"])

    def test_verify_fail_then_wall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            fail_cmd = f"{sys.executable} -c \"raise SystemExit(1)\""
            settings = self._write_settings(td, [fail_cmd])
            r1 = run_cli(["verify", "--settings", str(settings)], td)
            self.assertEqual(r1.returncode, 1, r1.stdout + r1.stderr)
            r2 = run_cli(["verify", "--settings", str(settings)], td)
            self.assertEqual(r2.returncode, 2, r2.stdout + r2.stderr)
            self.assertIn("WALL", r2.stdout)
            self.assertIn("SYSTEM_GAP", r2.stdout)
            state = json.loads((td / ".mk-agentos" / "loop-state.json").read_text())
            self.assertTrue(state["wall_hit"])
            self.assertEqual(state["consecutive_verify_failures"], 2)

    def test_done_gate_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            settings = self._write_settings(
                td, [f"{sys.executable} -c \"raise SystemExit(0)\""]
            )
            r = run_cli(["done-gate", "--settings", str(settings)], td)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("done-gate: OPEN", r.stdout)

    def test_empty_commands_exit_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            settings = {
                "profile": "solo",
                "project": {"root": ".", "name": "x"},
            }
            path = td / "settings.json"
            path.write_text(json.dumps(settings), encoding="utf-8")
            r = run_cli(["verify", "--settings", str(path)], td)
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)

    def test_wrap_gap_none_after_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            settings = self._write_settings(
                td, [f"{sys.executable} -c \"raise SystemExit(0)\""]
            )
            run_cli(["verify", "--settings", str(settings)], td)
            r = run_cli(["wrap-gap", "--settings", str(settings)], td)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("system-gap: none", r.stdout)
            self.assertNotIn("skipped", r.stdout)

    def test_wrap_gap_solo_no_verify_is_none_or_concrete(self) -> None:
        """solo with empty commands: never 'skipped'; after verify attempt, concrete gap."""
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            settings = {
                "profile": "solo",
                "project": {"root": ".", "name": "solo-empty"},
            }
            path = td / "settings.json"
            path.write_text(json.dumps(settings), encoding="utf-8")
            run_cli(["verify", "--settings", str(path)], td)
            r = run_cli(["wrap-gap", "--settings", str(path)], td)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("skipped", r.stdout)
            self.assertTrue(
                "system-gap: none" in r.stdout or "SYSTEM_GAP" in r.stdout,
                r.stdout,
            )
            self.assertIn("SYSTEM_GAP", r.stdout)

    def test_wrap_gap_after_wall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            fail_cmd = f"{sys.executable} -c \"raise SystemExit(1)\""
            settings = self._write_settings(td, [fail_cmd])
            run_cli(["verify", "--settings", str(settings)], td)
            run_cli(["verify", "--settings", str(settings)], td)
            r = run_cli(["wrap-gap", "--settings", str(settings)], td)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("SYSTEM_GAP", r.stdout)

    def test_reset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            fail_cmd = f"{sys.executable} -c \"raise SystemExit(1)\""
            settings = self._write_settings(td, [fail_cmd])
            run_cli(["verify", "--settings", str(settings)], td)
            run_cli(["verify", "--settings", str(settings)], td)
            r = run_cli(["reset", "--settings", str(settings)], td)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            state = json.loads((td / ".mk-agentos" / "loop-state.json").read_text())
            self.assertEqual(state["consecutive_verify_failures"], 0)
            self.assertFalse(state["wall_hit"])

    def test_resolved_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            settings = self._write_settings(
                td, [f"{sys.executable} -c \"raise SystemExit(0)\""]
            )
            resolved = td / "resolved.json"
            c = subprocess.run(
                [
                    sys.executable,
                    str(SETTINGS_CLI),
                    "compile",
                    "--settings",
                    str(settings),
                    "-o",
                    str(resolved),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
            r = run_cli(["verify", "--resolved", str(resolved)], td)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
