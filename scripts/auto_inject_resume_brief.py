#!/usr/bin/env python3
"""Claude Code SessionStart Hook: auto-inject Engram resume brief.

v3.30 mechanism (6) — the "last mile" that makes cross-session and
cross-tool resume zero-effort for the user. When Claude Code starts a
new session, this hook reads the cwd from the hook stdin payload, asks
Engram for ``get_resume_brief(project_folder=cwd)``, and emits the
result via the ``hookSpecificOutput.additionalContext`` JSON protocol.
Claude Code splices that text into the system prompt for the first user
turn, so the AI knows what the previous session was doing without the
user having to say "接着上次".

Wired by ``engram setup`` (via ``_inject_claude_code_sessionstart_hook``).

Re-entry guard: if ``CLAUDE_INVOKED_BY`` is set to ``engram_recursive``,
exit silently — the parent already produced the brief and a child
Claude Agent SDK invocation must not loop.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> None:
    # Re-entry guard (see auto_save_on_stop.py for rationale).
    if os.environ.get("CLAUDE_INVOKED_BY") == "engram_recursive":
        # Emit empty additionalContext to satisfy the hook contract.
        print(json.dumps({"continue": True}))
        return
    if os.environ.get("CLAUDE_INVOKED_BY", "").startswith("engram_"):
        os.environ["CLAUDE_INVOKED_BY"] = "engram_recursive"

    # Read hook input from stdin
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        hook_input = {}

    cwd = hook_input.get("cwd", "")

    # Locate the Engram source (dev tree first, then installed package)
    engram_src = Path(__file__).resolve().parent.parent / "src"
    if engram_src.is_dir() and str(engram_src) not in sys.path:
        sys.path.insert(0, str(engram_src))

    try:
        from piia_engram.core import Engram
        engram = Engram()
        # Keep budget snug so the additionalContext payload doesn't
        # dominate the first turn. 1500 tokens ≈ 6000 chars is plenty
        # for identity + project snapshot + a few lessons.
        brief = engram.get_resume_brief(
            project_folder=cwd or "",
            token_budget=1500,
        )
        markdown = brief.get("markdown", "")
    except Exception:
        # Hooks must never crash Claude Code. Empty additionalContext
        # is a safe no-op — Claude Code just behaves as if no hook fired.
        print(json.dumps({"continue": True}))
        return

    if not markdown:
        print(json.dumps({"continue": True}))
        return

    output = {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": markdown,
        },
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
