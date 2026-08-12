#!/usr/bin/env python3
"""Fail if agent-contract-kit tree contains home-lab / private host leakage.

Scans code, tests, templates, skills, hooks, spec.
Docs that document the denylist (PORTABILITY/DESIGN/README) are excluded.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]

# Private infra / org coupling that must not ship in portable kit *code*.
# Patterns built so this file itself is not a false positive.
_PAT = {
    "ip100": r"\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    "ip192": r"\b192\.168\.\d{1,3}\.\d{1,3}\b",
    "ip10": r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    # 172.16.0.0 – 172.31.255.255
    "ip172": r"\b172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}\b",
    "co": "91" + "app",
    "m2": r"\bmini" + r"2(-ts)?\b",
    "dgx": r"\bdgx" + r"-ts\b",
    "home": "/Users/" + "maki" + r"\b",
}
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("rfc1918_or_tailscale_ip", re.compile(_PAT["ip100"])),
    ("rfc1918_192", re.compile(_PAT["ip192"])),
    ("rfc1918_10", re.compile(_PAT["ip10"])),
    ("rfc1918_172", re.compile(_PAT["ip172"])),
    ("company_token", re.compile(_PAT["co"], re.I)),
    ("host_mini_secondary", re.compile(_PAT["m2"], re.I)),
    ("host_dgx_alias", re.compile(_PAT["dgx"], re.I)),
    ("users_home_path", re.compile(_PAT["home"])),
]


def scan_text(text: str) -> list[tuple[str, str]]:
    """Return list of (label, match) for testing."""
    hits: list[tuple[str, str]] = []
    for label, cre in PATTERNS:
        for m in cre.finditer(text):
            hits.append((label, m.group(0)))
    return hits
# exclude self from scan
SKIP_FILES = {
    "cli/ack_portability_lint.py",
    "tests/test_portability_lint.py",  # negative fixtures for scan_text()
}

SCAN_DIRS = ("cli", "hooks", "tests", "templates", "skills", "spec", "adapters")
SCAN_ROOT_FILES = ("settings.example.json",)

# Files allowed to *mention* denylist as documentation of what is forbidden
DOC_ALLOW = {
    "docs/PORTABILITY.md",
    "DESIGN.md",
    "README.md",
    "docs/PUBLIC.md",
}


def iter_files() -> list[Path]:
    files: list[Path] = []
    for name in SCAN_DIRS:
        d = KIT / name
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix in {
                ".py",
                ".md",
                ".json",
                ".yaml",
                ".yml",
                ".sh",
                ".txt",
            }:
                files.append(p)
    for name in SCAN_ROOT_FILES:
        p = KIT / name
        if p.is_file():
            files.append(p)
    return files


def main() -> int:
    failures: list[str] = []
    for path in iter_files():
        rel = path.relative_to(KIT).as_posix()
        if rel in DOC_ALLOW or rel in SKIP_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            failures.append(f"{rel}: read error {exc}")
            continue
        for label, cre in PATTERNS:
            for m in cre.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                failures.append(f"{rel}:{line}: {label}: {m.group(0)!r}")

    if failures:
        print("PORTABILITY LINT FAIL")
        for f in failures:
            print(" ", f)
        print(f"\n{len(failures)} hit(s). Remove private hosts/paths from kit code.")
        return 1
    print("PORTABILITY LINT OK")
    print(f"scanned under {KIT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
