#!/usr/bin/env python3
"""Legacy shim — delegates to ``piia_engram.hooks.auto_inject_resume_brief``."""

from __future__ import annotations

import sys
from pathlib import Path

_engram_src = Path(__file__).resolve().parent.parent / "src"
if _engram_src.is_dir() and str(_engram_src) not in sys.path:
    sys.path.insert(0, str(_engram_src))

from piia_engram.hooks.auto_inject_resume_brief import main

if __name__ == "__main__":
    main()
