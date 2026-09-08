#!/usr/bin/env python3
"""Ensure portability lint script exits 0 on clean kit tree + rejects private IPs."""

from __future__ import annotations

import subprocess
import sys
import unittest
import os
import hashlib
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
os.environ["PYTHONPATH"] = str(KIT / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")
LINT = ["-m", "ack.cli", "portability-lint"]
from ack import portability_lint as lint


class TestPortabilityLint(unittest.TestCase):
    def test_lint_clean(self) -> None:
        r = subprocess.run(
            [sys.executable, *LINT],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PORTABILITY LINT OK", r.stdout)

    def test_repo_and_package_modes(self) -> None:
        repo = lint.iter_files()
        self.assertEqual(repo[0], "repo")
        repo_names = {name for _, name in repo[2]}
        self.assertTrue(any(name.startswith("tests/") for name in repo_names))
        self.assertTrue(any(name.startswith("skills/") for name in repo_names))
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, *LINT], cwd=tmp, capture_output=True, text=True, check=False
            )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(proc.stdout.startswith("PORTABILITY LINT MODE: package mode"))

    def test_root_settings_matches_packaged_asset(self) -> None:
        root = KIT / "settings.example.json"
        asset = KIT / "src" / "ack" / "_assets" / "settings.example.json"
        self.assertEqual(hashlib.sha256(root.read_bytes()).hexdigest(), hashlib.sha256(asset.read_bytes()).hexdigest())

    def test_rejects_private_ips(self) -> None:
        # Build samples without storing denylist literals in scanned tree files
        # (this test file is skip-listed, but keep construction defensive).
        samples = {
            ".".join(["10", "0", "0", "8"]): "rfc1918_10",
            ".".join(["172", "16", "0", "8"]): "rfc1918_172",
            ".".join(["172", "31", "255", "254"]): "rfc1918_172",
            ".".join(["192", "168", "1", "1"]): "rfc1918_192",
            ".".join(["100", "89", "41", "50"]): "rfc1918_or_tailscale_ip",
        }
        for ip, label in samples.items():
            hits = lint.scan_text(f"endpoint {ip} ok")
            labels = {h[0] for h in hits}
            self.assertIn(label, labels, f"expected {label} for {ip}, got {hits}")

    def test_public_ip_not_flagged_as_rfc1918_10(self) -> None:
        hits = lint.scan_text("endpoint " + ".".join(["11", "0", "0", "1"]) + " ok")
        self.assertFalse(any(h[0] == "rfc1918_10" for h in hits))


if __name__ == "__main__":
    unittest.main()
