"""Engram Claude Code hooks.

This sub-package contains hook scripts that ship inside the wheel
(``src/piia_engram/hooks/``) so they can be reached via ``python -m
piia_engram.hooks.<name>`` after ``pip install piia-engram``. The legacy
copies under ``scripts/`` are kept as thin shims for backwards compat
but ``setup_wizard`` wires hooks to ``python -m`` invocations now.
"""
