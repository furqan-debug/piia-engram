#!/usr/bin/env python3
"""Legacy shim — delegates to ``piia_engram.hooks.auto_save_on_stop``.

Kept so existing ``settings.json`` entries that hard-code this path keep
working after upgrade. New installs use ``python -m`` invocation.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow dev-tree execution (when the package isn't installed yet) by
# putting src/ on sys.path before importing.
_engram_src = Path(__file__).resolve().parent.parent / "src"
if _engram_src.is_dir() and str(_engram_src) not in sys.path:
    sys.path.insert(0, str(_engram_src))

from piia_engram.hooks.auto_save_on_stop import main

if __name__ == "__main__":
    main()
