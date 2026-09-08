#!/usr/bin/env python3
"""Deprecated compatibility shim; use ``ack settings``."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ack.settings import main

if __name__ == "__main__":
    raise SystemExit(main())
