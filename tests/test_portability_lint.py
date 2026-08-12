#!/usr/bin/env python3
"""Ensure portability lint script exits 0 on clean kit tree + rejects private IPs."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
LINT = KIT / "cli" / "ack_portability_lint.py"
sys.path.insert(0, str(KIT / "cli"))
import ack_portability_lint as lint  # noqa: E402


class TestPortabilityLint(unittest.TestCase):
    def test_lint_clean(self) -> None:
        r = subprocess.run(
            [sys.executable, str(LINT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PORTABILITY LINT OK", r.stdout)

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
