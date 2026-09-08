#!/usr/bin/env python3
"""Fail if agent-contract-kit tree contains home-lab / private host leakage.

Scans code, tests, templates, skills, hooks, spec.
Docs that document the denylist (PORTABILITY/DESIGN/README) are excluded.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent

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
    "src/ack/portability_lint.py",
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


def find_repo_root(cwd: Path) -> Path | None:
    """Find a checkout root without accepting a positional path argument."""
    cwd = cwd.resolve()
    for base in (cwd, *cwd.parents):
        if (base / "pyproject.toml").is_file() and (base / "src" / "ack").is_dir():
            return base
    return None


def iter_files() -> tuple[str, Path, list[tuple[Path, str]]]:
    root = find_repo_root(Path.cwd())
    if root is None:
        asset_files = [
            (p, p.relative_to(KIT).as_posix())
            for p in KIT.joinpath("_assets").rglob("*")
            if p.is_file()
            and (
                p.parent == KIT / "_assets" / "bin"
                or p.suffix in {".py", ".md", ".json", ".yaml", ".yml", ".sh", ".txt"}
            )
        ]
        return "package", KIT, asset_files

    # Preserve the old logical scan set while mapping shipped assets to their
    # package locations.  The cli shims remain included for compatibility.
    locations = {
        "cli": (root / "src" / "ack", root / "cli"),
        "hooks": (root / "src" / "ack" / "_assets" / "hooks",),
        "tests": (root / "tests",),
        "templates": (root / "src" / "ack" / "_assets" / "templates",),
        "skills": (root / "skills",),
        "spec": (root / "src" / "ack" / "_assets" / "spec",),
        "adapters": (root / "adapters",),
    }
    files: list[Path] = []
    for name in SCAN_DIRS:
        for d in locations[name]:
            if d.is_dir():
                files.extend(p for p in d.rglob("*") if p.is_file() and p.suffix in {
                    ".py", ".md", ".json", ".yaml", ".yml", ".sh", ".txt",
                })
    asset_bin = root / "src" / "ack" / "_assets" / "bin"
    if asset_bin.is_dir():
        files.extend(p for p in asset_bin.iterdir() if p.is_file())
    for name in SCAN_ROOT_FILES:
        p = root / name
        if p.is_file():
            files.append(p)
    return "repo", root, [(p, p.relative_to(root).as_posix()) for p in files]


def main(argv: list[str] | None = None) -> int:
    failures: list[str] = []
    mode, scan_root, files = iter_files()
    print(f"PORTABILITY LINT MODE: {mode} mode (scan root: {scan_root})")
    for path, rel in files:
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
    print(f"scanned under {scan_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
