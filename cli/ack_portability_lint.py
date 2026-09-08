#!/usr/bin/env python3
"""Deprecated compatibility shim; use ``ack portability-lint``."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ack.portability_lint import main

if __name__ == "__main__":
    raise SystemExit(main())
