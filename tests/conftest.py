"""Shared pytest fixtures for the Engram test suite."""

import os

import pytest


@pytest.fixture(autouse=True)
def _suppress_fragmentation_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Suppress DATA FRAGMENTATION warnings in tests.

    When tests create a temporary ENGRAM_DIR, the real ~/.engram still
    exists on the developer's machine, triggering a noisy warning on
    every Engram() init.  ENGRAM_TEST=1 tells core.py to skip the
    fragmentation check.
    """
    monkeypatch.setenv("ENGRAM_TEST", "1")
