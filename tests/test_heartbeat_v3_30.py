"""v3.30 mechanism (2) — time-based heartbeat snapshot guardrail tests.

Engram v3.28.1 already saves a checkpoint every 20 non-cold-start tool calls
(``_SessionTracker._CHECKPOINT_EVERY``). The remaining gap exposed on
2026-05-27 was: if a session is idle for an hour (tool calls < 20) and the
process is then killed, atexit may not run and everything is lost.

v3.30 adds a background daemon thread that triggers ``_interim_save`` on a
time interval (``ENGRAM_HEARTBEAT_INTERVAL`` seconds, default 300, set 0 to
disable). These tests pin that behavior so future refactors can't silently
regress it.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from piia_engram import mcp_server
from piia_engram.core import Engram


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_tracker(monkeypatch, tmp_path: Path, interval: str | None) -> "mcp_server._SessionTracker":
    """Create an isolated _SessionTracker with the requested heartbeat interval.

    Uses a tmp_path-backed Engram so checkpoints don't pollute ~/.engram/.
    Caller is responsible for setting tracker._stop_event to shut down the
    daemon thread before the test exits (otherwise pytest may hang briefly
    waiting for thread cleanup — daemon=True means it can't block exit but
    polite teardown is faster).
    """
    if interval is None:
        monkeypatch.delenv("ENGRAM_HEARTBEAT_INTERVAL", raising=False)
    else:
        monkeypatch.setenv("ENGRAM_HEARTBEAT_INTERVAL", interval)

    monkeypatch.setattr(mcp_server, "_engram", Engram(root=tmp_path))
    return mcp_server._SessionTracker()


def _shutdown(tracker) -> None:
    tracker._stop_event.set()
    if tracker._heartbeat_thread is not None:
        tracker._heartbeat_thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# Configuration parsing
# ---------------------------------------------------------------------------


def test_default_heartbeat_interval_is_300_seconds(monkeypatch, tmp_path: Path):
    """Spec: 5 minutes by default, matching the v3.30 design doc."""
    tracker = _fresh_tracker(monkeypatch, tmp_path, interval=None)
    try:
        assert tracker._heartbeat_interval == 300
        assert tracker._heartbeat_thread is not None
        assert tracker._heartbeat_thread.is_alive()
    finally:
        _shutdown(tracker)


def test_heartbeat_disabled_when_env_is_zero(monkeypatch, tmp_path: Path):
    """ENGRAM_HEARTBEAT_INTERVAL=0 must fully disable the background thread."""
    tracker = _fresh_tracker(monkeypatch, tmp_path, interval="0")
    try:
        assert tracker._heartbeat_interval == 0
        assert tracker._heartbeat_thread is None
    finally:
        _shutdown(tracker)


def test_heartbeat_disabled_when_env_is_negative(monkeypatch, tmp_path: Path):
    tracker = _fresh_tracker(monkeypatch, tmp_path, interval="-5")
    try:
        assert tracker._heartbeat_interval == 0
        assert tracker._heartbeat_thread is None
    finally:
        _shutdown(tracker)


def test_heartbeat_falls_back_to_default_on_garbage_env(monkeypatch, tmp_path: Path):
    """Invalid env var must not crash startup — fall back to the default."""
    tracker = _fresh_tracker(monkeypatch, tmp_path, interval="not-a-number")
    try:
        assert tracker._heartbeat_interval == 300
    finally:
        _shutdown(tracker)


def test_heartbeat_respects_minimum_floor(monkeypatch, tmp_path: Path):
    """Even with ENGRAM_HEARTBEAT_INTERVAL=1 the thread should accept it
    (we let users go aggressive in tests/dev), but values <= 0 are disabled."""
    tracker = _fresh_tracker(monkeypatch, tmp_path, interval="1")
    try:
        assert tracker._heartbeat_interval == 1
        assert tracker._heartbeat_thread is not None
    finally:
        _shutdown(tracker)


# ---------------------------------------------------------------------------
# Heartbeat triggers an actual checkpoint
# ---------------------------------------------------------------------------


def test_heartbeat_fires_checkpoint_on_idle_session_with_activity(
    monkeypatch, tmp_path: Path
):
    """The headline guarantee: if there are unsaved tool calls and the
    interval elapses, _interim_save runs without record() being called
    20 more times. This is what protects against crash-mid-idle-session."""
    tracker = _fresh_tracker(monkeypatch, tmp_path, interval="1")
    try:
        # Record only 2 real tool calls — far below _CHECKPOINT_EVERY=20.
        tracker.record("add_lesson", "lesson 1")
        tracker.record("add_decision", "decision 1")
        assert tracker._checkpoint_seq == 0  # no checkpoint yet

        # Wait > 2 intervals. The heartbeat thread should have fired at
        # least one checkpoint by now (1s interval, 2.5s wait).
        time.sleep(2.5)

        assert tracker._checkpoint_seq >= 1, (
            "Heartbeat must trigger _interim_save even when call count "
            "is below _CHECKPOINT_EVERY"
        )

        # The checkpoint file should exist on disk under contexts/.
        ctx_dir = tmp_path / "contexts" / "mcp_auto"
        assert ctx_dir.is_dir()
        cp_files = list(ctx_dir.glob("*-cp*.md"))
        assert cp_files, f"Expected checkpoint .md file, found: {list(ctx_dir.iterdir())}"
        body = cp_files[0].read_text(encoding="utf-8")
        assert "触发: heartbeat" in body, (
            "Checkpoint header must tag the trigger reason so audits can "
            "distinguish heartbeat vs count vs manual saves"
        )
    finally:
        _shutdown(tracker)


def test_heartbeat_skips_when_no_activity(monkeypatch, tmp_path: Path):
    """An empty session must NOT spam checkpoints. We waste IO otherwise."""
    tracker = _fresh_tracker(monkeypatch, tmp_path, interval="1")
    try:
        time.sleep(2.5)  # >2 intervals elapse with no activity
        assert tracker._checkpoint_seq == 0
    finally:
        _shutdown(tracker)


def test_heartbeat_skips_when_already_saved(monkeypatch, tmp_path: Path):
    """After a record-triggered checkpoint, the next heartbeat tick should
    NOT fire another save unless there's new activity. Otherwise long
    sessions would get a checkpoint every interval, doubling the work."""
    tracker = _fresh_tracker(monkeypatch, tmp_path, interval="1")
    try:
        tracker.record("add_lesson", "lesson 1")
        tracker.record("add_decision", "decision 1")
        # Manual save to set _last_save_at = now
        tracker._interim_save()
        seq_after_manual = tracker._checkpoint_seq
        assert seq_after_manual >= 1

        # No new record() — heartbeat should be a no-op for at least one tick.
        time.sleep(1.5)
        assert tracker._checkpoint_seq == seq_after_manual
    finally:
        _shutdown(tracker)


def test_heartbeat_resumes_after_new_activity(monkeypatch, tmp_path: Path):
    """After a quiet period, a new record() should cause the next heartbeat
    tick to fire again. (Catches: 'thread misreads _last_save_at and never
    fires again' bug.)

    Uses 2s sleeps (vs 1s interval) to give the thread enough margin for
    startup latency + GIL scheduling + disk write on slow Windows runners.
    """
    tracker = _fresh_tracker(monkeypatch, tmp_path, interval="1")
    try:
        tracker.record("add_lesson", "first")
        time.sleep(2.0)
        first_seq = tracker._checkpoint_seq
        assert first_seq >= 1, (
            f"Expected at least one heartbeat checkpoint after 2s with 1s "
            f"interval, but _checkpoint_seq={first_seq}. Heartbeat thread "
            f"may not have fired."
        )

        # New activity 2s later. Heartbeat should fire again within ~1s.
        tracker.record("add_decision", "second")
        time.sleep(2.0)
        assert tracker._checkpoint_seq > first_seq, (
            f"Heartbeat should fire again after new record() activity, but "
            f"_checkpoint_seq stayed at {first_seq}"
        )
    finally:
        _shutdown(tracker)


# ---------------------------------------------------------------------------
# Concurrency safety
# ---------------------------------------------------------------------------


def test_concurrent_record_and_heartbeat_does_not_corrupt_state(
    monkeypatch, tmp_path: Path
):
    """Record and heartbeat both touch self.calls and self._checkpoint_seq.
    With proper locking, hammering record() while heartbeat is firing must
    produce a consistent final state (no exceptions, no lost calls)."""
    tracker = _fresh_tracker(monkeypatch, tmp_path, interval="1")

    n_calls = 100
    errors: list[Exception] = []

    def worker() -> None:
        try:
            for i in range(n_calls):
                tracker.record(f"tool_{i % 5}", f"args_{i}")
                time.sleep(0.005)
        except Exception as exc:
            errors.append(exc)

    try:
        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Concurrent record raised: {errors}"
        # 3 workers × 100 calls = exactly 300 entries
        assert len(tracker.calls) == 3 * n_calls
        # Heartbeat should have fired at least once during the ~3s run.
        assert tracker._checkpoint_seq >= 1
    finally:
        _shutdown(tracker)


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


def test_auto_save_stops_the_heartbeat_thread(monkeypatch, tmp_path: Path):
    """auto_save() must signal the heartbeat thread to exit so atexit doesn't
    race a final save. Daemon=True alone would leak briefly during shutdown."""
    tracker = _fresh_tracker(monkeypatch, tmp_path, interval="1")
    try:
        tracker.record("add_lesson", "x")
        tracker.record("add_decision", "y")
        # _MIN_CALLS=2 → auto_save should actually run
        tracker.auto_save()
        assert tracker._stop_event.is_set()
        if tracker._heartbeat_thread is not None:
            tracker._heartbeat_thread.join(timeout=2.0)
            assert not tracker._heartbeat_thread.is_alive()
    finally:
        _shutdown(tracker)
