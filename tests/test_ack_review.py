#!/usr/bin/env python3
"""Tests for ack_review filesystem dual-review adapter."""

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
CLI = ["-m", "ack.cli", "review"]


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *CLI, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def dual_settings(td: Path) -> Path:
    settings = {
        "profile": "dual-review",
        "project": {"root": ".", "name": "rev"},
        "verify": {"commands": [f"{sys.executable} -c \"raise SystemExit(0)\""]},
        "layers": {
            "graph": {
                "agents": {"executor": "claude", "reviewer": "codex"},
            }
        },
    }
    p = td / "settings.json"
    p.write_text(json.dumps(settings), encoding="utf-8")
    return p


GOOD_BRIEFING = """# Dual-review briefing

## TASK
Implement feature X and add tests.

## CONTEXT
Repo module foo/; related issue #12.

## CONSTRAINTS
Do not refactor bar/; no new dependencies.

## VERIFY
Run unit tests for foo and lint.

## PATHS_OR_DIFF_STAT
foo/a.py
foo/a_test.py
git diff --stat shows 2 files
"""

GOOD_ANSWER_PASS = """# Reviewer answer

## Summary
Looks good.

VERDICT: PASS

## EVIDENCE
diff: foo/a.py
test: foo/a_test.py passed
"""

GOOD_ANSWER_FAIL = """# Reviewer answer

VERDICT: FAIL

## EVIDENCE
path: foo/a.py missing edge case test
"""


class TestAckReview(unittest.TestCase):
    def test_solo_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            settings = {
                "profile": "solo-strict",
                "project": {"root": ".", "name": "s"},
                "verify": {"commands": ["true"]},
            }
            sp = td / "settings.json"
            sp.write_text(json.dumps(settings), encoding="utf-8")
            r = run(["init", "--settings", str(sp)], td)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("REFUSED", r.stderr + r.stdout)

    def test_init_and_check_briefing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            sp = dual_settings(td)
            r = run(["init", "--settings", str(sp), "--session", "s1"], td)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            # template incomplete
            r2 = run(["check-briefing", "--settings", str(sp), "--session", "s1"], td)
            self.assertNotEqual(r2.returncode, 0)
            sdir = td / ".mk-agentos" / "reviews" / "s1"
            (sdir / "briefing.md").write_text(GOOD_BRIEFING, encoding="utf-8")
            r3 = run(["check-briefing", "--settings", str(sp), "--session", "s1"], td)
            self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
            self.assertIn("BRIEFING OK", r3.stdout)

    def test_handoff_and_accept(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            sp = dual_settings(td)
            run(["init", "--settings", str(sp), "--session", "s2"], td)
            sdir = td / ".mk-agentos" / "reviews" / "s2"
            (sdir / "briefing.md").write_text(GOOD_BRIEFING, encoding="utf-8")
            h = run(["handoff-gate", "--settings", str(sp), "--session", "s2"], td)
            self.assertEqual(h.returncode, 0, h.stdout + h.stderr)
            self.assertIn("HANDOFF OPEN", h.stdout)
            # no answer yet
            a0 = run(["accept-gate", "--settings", str(sp), "--session", "s2"], td)
            self.assertNotEqual(a0.returncode, 0)
            self.assertIn("self-accept", a0.stderr + a0.stdout)
            (sdir / "answer.md").write_text(GOOD_ANSWER_PASS, encoding="utf-8")
            ca = run(["check-answer", "--settings", str(sp), "--session", "s2"], td)
            self.assertEqual(ca.returncode, 0, ca.stdout + ca.stderr)
            a1 = run(["accept-gate", "--settings", str(sp), "--session", "s2"], td)
            self.assertEqual(a1.returncode, 0, a1.stdout + a1.stderr)
            self.assertIn("ACCEPT OPEN", a1.stdout)

    def test_handoff_returns_loop_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            sp = dual_settings(td)
            data = json.loads(sp.read_text(encoding="utf-8"))
            data["verify"] = {"commands": [f"{sys.executable} -c \"raise SystemExit(7)\""]}
            sp.write_text(json.dumps(data), encoding="utf-8")
            run(["init", "--settings", str(sp), "--session", "failed-loop"], td)
            sdir = td / ".mk-agentos" / "reviews" / "failed-loop"
            (sdir / "briefing.md").write_text(GOOD_BRIEFING, encoding="utf-8")
            result = run(["handoff-gate", "--settings", str(sp), "--session", "failed-loop"], td)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("VERIFY FAIL", result.stdout + result.stderr)

    def test_accept_fail_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            sp = dual_settings(td)
            run(["init", "--settings", str(sp), "--session", "s3"], td)
            sdir = td / ".mk-agentos" / "reviews" / "s3"
            (sdir / "briefing.md").write_text(GOOD_BRIEFING, encoding="utf-8")
            h = run(["handoff-gate", "--settings", str(sp), "--session", "s3"], td)
            self.assertEqual(h.returncode, 0, h.stdout + h.stderr)
            (sdir / "answer.md").write_text(GOOD_ANSWER_FAIL, encoding="utf-8")
            a = run(["accept-gate", "--settings", str(sp), "--session", "s3"], td)
            self.assertNotEqual(a.returncode, 0)
            self.assertIn("FAIL", a.stdout + a.stderr)

    def test_check_answer_missing_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            sp = dual_settings(td)
            run(["init", "--settings", str(sp), "--session", "s4"], td)
            sdir = td / ".mk-agentos" / "reviews" / "s4"
            (sdir / "answer.md").write_text("looks fine\n", encoding="utf-8")
            r = run(["check-answer", "--settings", str(sp), "--session", "s4"], td)
            self.assertNotEqual(r.returncode, 0)

    def test_handoff_rejects_template_briefing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            sp = dual_settings(td)
            run(["init", "--settings", str(sp), "--session", "s5"], td)
            # leave default template
            h = run(["handoff-gate", "--settings", str(sp), "--session", "s5"], td)
            self.assertNotEqual(h.returncode, 0)
            self.assertIn("briefing", (h.stderr + h.stdout).lower())

    def test_accept_requires_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            sp = dual_settings(td)
            run(["init", "--settings", str(sp), "--session", "s6"], td)
            sdir = td / ".mk-agentos" / "reviews" / "s6"
            (sdir / "briefing.md").write_text(GOOD_BRIEFING, encoding="utf-8")
            (sdir / "answer.md").write_text(GOOD_ANSWER_PASS, encoding="utf-8")
            # skip handoff-gate
            a = run(["accept-gate", "--settings", str(sp), "--session", "s6"], td)
            self.assertNotEqual(a.returncode, 0)
            self.assertIn("handoff", (a.stderr + a.stdout).lower())


if __name__ == "__main__":
    unittest.main()
