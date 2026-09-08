"""Console-script wrappers for the bundled capability gateway shell tools.

The shell tools must run from their resource directory: they source helper files
beside themselves and ``cap`` routes to sibling scripts.  ``as_file`` supplies a
real path both from a source checkout and from an installed wheel.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from importlib.resources import as_file, files


def run_tool(name: str, args: Sequence[str] | None = None) -> int:
    """Run a packaged shell tool through bash, preserving the caller's streams."""
    tool_args = list(sys.argv[1:] if args is None else args)
    # Materialize the whole bin directory, not a single file: the tools source
    # sibling helpers (_cap_lib, _cap_audit, _audit_log) via SCRIPT_DIR, which
    # would be missing if only one file were extracted from a zipped package.
    bin_dir = files("ack").joinpath("_assets", "bin")
    with as_file(bin_dir) as path:
        return subprocess.run(["bash", str(path / name), *tool_args], check=False).returncode


def cap() -> int:
    return run_tool("cap")


def cap_check() -> int:
    return run_tool("cap-check")


def cap_go() -> int:
    return run_tool("cap-go")


def safe_move() -> int:
    return run_tool("safe_move")


def safe_rsync() -> int:
    return run_tool("safe_rsync")


def main(argv: Sequence[str] | None = None) -> int:
    """Support ``python -m ack.capcli <tool> [args...]`` for test environments."""
    values = list(sys.argv[1:] if argv is None else argv)
    if not values or values[0] not in TOOLS:
        print("Usage: python -m ack.capcli {cap|cap-check|cap-go|safe_move|safe_rsync} [args...]")
        return 2
    return run_tool(values[0], values[1:])


TOOLS = {"cap", "cap-check", "cap-go", "safe_move", "safe_rsync"}


if __name__ == "__main__":
    raise SystemExit(main())
