"""Black-box checks for capability-gateway package wrappers.

Prerequisites on the host: bash, rsync, jq, date, realpath (the gateway scripts
are POSIX shell tools). Every subprocess runs with HOME pointed at a temp dir so
nothing is written to the real ~/.agent_audit.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
ENV = os.environ.copy()
ENV["PYTHONPATH"] = str(KIT / "src") + os.pathsep + ENV.get("PYTHONPATH", "")


def run_tool(tool: str, *args: str, home: Path) -> subprocess.CompletedProcess[str]:
    env = ENV | {"HOME": str(home)}
    return subprocess.run(
        [sys.executable, "-m", "ack.capcli", tool, *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


class TestCapConsoleWrappers(unittest.TestCase):
    def test_classify_risks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            red = run_tool("cap", "classify", "rm", "-rf", "/tmp/build", home=home)
            unknown = run_tool("cap", "classify", "ls", "-la", home=home)
        self.assertEqual(red.returncode, 0, red.stderr)
        self.assertIn("RED", red.stdout)
        self.assertEqual(unknown.returncode, 0, unknown.stderr)
        self.assertIn("BLOCKED", unknown.stdout)

    def test_check_creates_plan_and_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            source = Path(tmp) / "source"
            destination = Path(tmp) / "destination"
            source.mkdir()
            source.joinpath("example.txt").write_text("content", encoding="utf-8")
            result = run_tool("cap", "check", "rsync", "-av", f"{source}/", f"{destination}/", home=home)
            plans = list((home / ".agent_audit" / "plans").glob("P-*.json"))
            log = home / ".agent_audit" / "logs" / f"{date.today():%Y-%m-%d}.jsonl"
            log_exists = log.is_file()
            log_content = log.read_text(encoding="utf-8") if log_exists else ""
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("plan_id", result.stdout)
        self.assertEqual(len(plans), 1)
        self.assertTrue(log_exists)
        self.assertTrue(log_content.strip())

    def test_safe_rsync_blocks_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_tool("safe_rsync", "--delete", "a", "b", home=Path(tmp))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Delete flag", result.stdout)

    def test_all_wrappers_reach_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cases = {
                "cap": ("help",),
                "cap-check": (),
                "cap-go": (),
                "safe_move": (),
                "safe_rsync": (),
            }
            for tool, args in cases.items():
                with self.subTest(tool=tool):
                    result = run_tool(tool, *args, home=home)
                    self.assertIn("Usage", result.stdout)


if __name__ == "__main__":
    unittest.main()
