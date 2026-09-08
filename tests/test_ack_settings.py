#!/usr/bin/env python3
"""Tests for cli/ack_settings.py — run: python3 -m pytest or direct."""

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
CLI = ["-m", "ack.cli", "settings"]
SCHEMA = KIT / "src" / "ack" / "_assets" / "spec" / "settings.schema.json"
ROOT_EXAMPLE = KIT / "settings.example.json"
PKG_EXAMPLE = KIT / "settings.example.json"

from ack import settings as ack_settings


class TestAckSettings(unittest.TestCase):
    def test_root_example_validate(self) -> None:
        r = subprocess.run(
            [
                sys.executable,
                *CLI,
                "validate",
                "--settings",
                str(ROOT_EXAMPLE),
                "--schema",
                str(SCHEMA),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_pkg_example_validate(self) -> None:
        r = subprocess.run(
            [
                sys.executable,
                *CLI,
                "validate",
                "--settings",
                str(PKG_EXAMPLE),
                "--schema",
                str(SCHEMA),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_compile_unions_secrets(self) -> None:
        raw = {
            "profile": "solo-strict",
            "verify": {"commands": ["true"]},
            "human": {"require_confirm_for": ["git_push"]},
        }
        eff = ack_settings.compile_settings(raw)
        self.assertIn("secrets", eff["human"]["require_confirm_for"])
        self.assertIn("git_push", eff["human"]["require_confirm_for"])

    def test_strict_requires_verify(self) -> None:
        with self.assertRaises(ValueError):
            ack_settings.compile_settings({"profile": "solo-strict"})

    def test_solo_allows_empty_verify(self) -> None:
        eff = ack_settings.compile_settings({"profile": "solo"})
        self.assertEqual(eff["layers"]["loop"]["verify"]["commands"], [])

    def test_top_verify_overrides(self) -> None:
        eff = ack_settings.compile_settings(
            {
                "profile": "solo-strict",
                "verify": {"commands": ["pytest -q"]},
            }
        )
        self.assertEqual(
            eff["layers"]["loop"]["verify"]["commands"], ["pytest -q"]
        )

    def test_memory_enabled_none_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ack_settings.compile_settings(
                {
                    "profile": "solo",
                    "layers": {
                        "context": {
                            "memory": {"enabled": True, "backend": "none"}
                        }
                    },
                }
            )

    def test_solo_dual_edges_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ack_settings.compile_settings(
                {
                    "profile": "solo",
                    "layers": {
                        "graph": {
                            "mode": "solo",
                            "edges": "builtin:dual-review",
                        }
                    },
                }
            )

    def test_dual_review_requires_agents(self) -> None:
        with self.assertRaises(ValueError):
            ack_settings.compile_settings(
                {
                    "profile": "dual-review",
                    "verify": {"commands": ["true"]},
                }
            )
        with self.assertRaises(ValueError):
            ack_settings.compile_settings(
                {
                    "profile": "dual-review",
                    "verify": {"commands": ["true"]},
                    "layers": {
                        "graph": {
                            "agents": {"executor": "", "reviewer": "codex"}
                        }
                    },
                }
            )
        eff = ack_settings.compile_settings(
            {
                "profile": "dual-review",
                "verify": {"commands": ["true"]},
                "layers": {
                    "graph": {
                        "agents": {
                            "executor": "claude",
                            "reviewer": "codex",
                        }
                    }
                },
            }
        )
        self.assertEqual(eff["layers"]["graph"]["mode"], "dual-review")

    def test_custom_allows_arbitrary_agents(self) -> None:
        eff = ack_settings.compile_settings(
            {
                "profile": "solo",
                "layers": {
                    "graph": {
                        "mode": "custom",
                        "edges": "graphs/my.yaml",
                        "agents": {"planner": "claude", "worker": "codex"},
                    }
                },
            }
        )
        self.assertEqual(eff["layers"]["graph"]["mode"], "custom")

    def test_compile_cli_writes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "resolved.json"
            r = subprocess.run(
                [
                    sys.executable,
                    *CLI,
                    "compile",
                    "--settings",
                    str(ROOT_EXAMPLE),
                    "--schema",
                    str(SCHEMA),
                    "-o",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            data = json.loads(out.read_text())
            self.assertEqual(data["profile"], "solo-strict")
            self.assertIn("secrets", data["human"]["require_confirm_for"])


if __name__ == "__main__":
    unittest.main()
