"""v3.30 mechanism (1) — unclean-exit detection guardrail tests.

session_state.json is the breadcrumb Engram leaves at init time
(last_clean_exit=False) and rewrites at atexit (last_clean_exit=True).
A new Engram instance reading the breadcrumb left by a prior killed
process is what powers the doctor "previous session may have ended
unexpectedly" warning.
"""

from __future__ import annotations

from pathlib import Path

from piia_engram.core import Engram


def _make(tmp_path: Path) -> Engram:
    return Engram(root=tmp_path)


def test_session_state_file_created_at_init(tmp_path: Path):
    e = _make(tmp_path)
    state_path = e._session_state_path
    assert state_path.is_file()
    import json
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["pid"] > 0
    assert data["last_clean_exit"] is False
    assert data["started_at"]


def test_fresh_install_reports_no_unclean_exit(tmp_path: Path):
    """First Engram() ever — there is no prior state, doctor must not warn."""
    e = _make(tmp_path)
    # _prev_unclean is captured at init from any pre-existing file. Fresh
    # tmp_path has none, so it should be None.
    assert getattr(e, "_prev_unclean", None) is None
    assert e.get_unclean_exit_marker() is None


def test_unclean_exit_detected_when_prior_did_not_mark_clean(tmp_path: Path):
    """Simulate: instance A starts, instance B starts before A marks clean.

    In real life A and B are different processes with different pids; here
    both share the same pid (the test runner), so we simulate the prior
    instance by manually rewriting the pid in the breadcrumb to something
    that is NOT the current pid.
    """
    e_a = _make(tmp_path)
    # Manually mutate the state to simulate "prior process with pid 999999".
    import json, os
    state_path = e_a._session_state_path
    data = json.loads(state_path.read_text(encoding="utf-8"))
    fake_prior_pid = 1 if os.getpid() != 1 else 2
    data["pid"] = fake_prior_pid
    data["last_clean_exit"] = False
    state_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    # Now a "new" instance B starts in the same root.
    e_b = Engram(root=tmp_path)
    assert e_b._prev_unclean is not None
    assert e_b._prev_unclean["pid"] == fake_prior_pid


def test_clean_exit_clears_warning(tmp_path: Path):
    """After _mark_clean_exit, the next Engram() init must not see a warning."""
    e_a = _make(tmp_path)
    e_a._mark_clean_exit(last_session_id="test-session-1")
    e_b = Engram(root=tmp_path)
    assert e_b._prev_unclean is None
    assert e_b.get_unclean_exit_marker() is None


def test_mark_clean_exit_persists_session_id(tmp_path: Path):
    e = _make(tmp_path)
    e._mark_clean_exit(last_session_id="session-xyz")
    import json
    data = json.loads(e._session_state_path.read_text(encoding="utf-8"))
    assert data["last_clean_exit"] is True
    assert data["last_session_id"] == "session-xyz"
    assert data["last_seen_at"]


def test_get_unclean_exit_marker_returns_dict_with_required_fields(tmp_path: Path):
    e_a = _make(tmp_path)
    # Same simulation as test 3: rewrite state's pid to a fake prior pid.
    import json, os
    data = json.loads(e_a._session_state_path.read_text(encoding="utf-8"))
    data["pid"] = 1 if os.getpid() != 1 else 2
    data["last_clean_exit"] = False
    e_a._session_state_path.write_text(json.dumps(data), encoding="utf-8")

    e_b = Engram(root=tmp_path)
    marker = e_b._prev_unclean
    assert marker is not None
    for key in ("pid", "started_at", "last_seen_at", "last_session_id"):
        assert key in marker


def test_mark_clean_exit_is_idempotent(tmp_path: Path):
    e = _make(tmp_path)
    e._mark_clean_exit()
    e._mark_clean_exit()
    e._mark_clean_exit()
    import json
    data = json.loads(e._session_state_path.read_text(encoding="utf-8"))
    assert data["last_clean_exit"] is True


def test_session_state_corruption_does_not_crash_init(tmp_path: Path):
    """A malformed session_state.json must not block Engram from starting."""
    _make(tmp_path)  # create initial file
    # Corrupt it
    (tmp_path / "session_state.json").write_text("not json {{{", encoding="utf-8")
    # New init must still succeed — get_unclean_exit_marker should fail safe.
    e = Engram(root=tmp_path)
    assert e._prev_unclean is None  # malformed = treated as unknown, not warned


# ---------------------------------------------------------------------------
# H5 — clean-exit ownership check.
# Multiple Engram processes can share a single ENGRAM_DIR. Process A's
# graceful exit must NOT erase process B's unclean-exit signal.
# ---------------------------------------------------------------------------


def test_mark_clean_exit_refuses_to_overwrite_other_process_marker(tmp_path: Path):
    """A's ``_mark_clean_exit`` must be a no-op when the breadcrumb on
    disk was written by B (different nonce). Otherwise B's eventual
    crash becomes invisible to doctor."""
    import json

    e_a = _make(tmp_path)
    # Simulate B taking over the breadcrumb by overwriting nonce + pid.
    state_path = e_a._session_state_path
    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["session_nonce"] = "deadbeefdeadbeef"
    data["pid"] = 999_999
    data["last_clean_exit"] = False
    state_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    # A's clean exit must not touch B's marker.
    e_a._mark_clean_exit(last_session_id="A-session")
    after = json.loads(state_path.read_text(encoding="utf-8"))
    assert after["last_clean_exit"] is False, (
        "A's _mark_clean_exit overwrote B's marker — H5 ownership check "
        "missing or broken"
    )
    assert after["session_nonce"] == "deadbeefdeadbeef"
    assert after.get("last_session_id", "") != "A-session"


def test_mark_clean_exit_still_works_for_owner(tmp_path: Path):
    """Sanity check that the H5 fix doesn't break the normal path: the
    process that wrote the marker can still clean-exit it."""
    import json

    e = _make(tmp_path)
    e._mark_clean_exit(last_session_id="my-session")
    data = json.loads(e._session_state_path.read_text(encoding="utf-8"))
    assert data["last_clean_exit"] is True
    assert data["last_session_id"] == "my-session"


# ---------------------------------------------------------------------------
# H1 (Codex final review): _owns_session_state must NOT match an old
# crashed marker whose pid was recycled by the OS. Before the fix, the
# legacy fallback (pid + started_at) would match because _session_nonce
# was not yet set during the get_unclean_exit_marker() call inside
# _mark_session_start().
# ---------------------------------------------------------------------------


def test_pid_reuse_with_nonce_does_not_suppress_crash_warning(tmp_path: Path):
    """H1 regression: Old process crashed (has nonce, same pid via reuse).

    A new Engram init must still surface the unclean-exit warning.
    Before the fix, ``_owns_session_state`` fell into the legacy
    pid-only fallback because the new instance's nonce was not yet set,
    incorrectly returning True and suppressing the warning.
    """
    import json
    import os

    e_a = _make(tmp_path)
    # Simulate: A crashed (last_clean_exit=False), AND the OS recycled
    # A's pid so the new process happens to get the same pid.
    state_path = e_a._session_state_path
    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["pid"] = os.getpid()  # same pid as the upcoming new instance
    data["last_clean_exit"] = False
    data["session_nonce"] = "oldcrashednonce1"  # different from new
    data["started_at"] = "2020-01-01T00:00:00"
    state_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    # New instance — its nonce is set AFTER get_unclean_exit_marker runs.
    e_b = Engram(root=tmp_path)
    assert e_b._prev_unclean is not None, (
        "H1 bug: pid-reuse + old nonce marker was incorrectly claimed "
        "as 'ours', suppressing the crash warning"
    )
    assert e_b._prev_unclean["pid"] == os.getpid()


def test_pre_nonce_legacy_marker_with_different_pid_detected(tmp_path: Path):
    """Pre-v3.30 marker (no nonce) from a different pid is detected."""
    import json
    import os

    e_a = _make(tmp_path)
    state_path = e_a._session_state_path
    data = json.loads(state_path.read_text(encoding="utf-8"))
    fake_pid = 1 if os.getpid() != 1 else 2
    data["pid"] = fake_pid
    data["last_clean_exit"] = False
    data.pop("session_nonce", None)  # simulate pre-v3.30
    state_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    e_b = Engram(root=tmp_path)
    assert e_b._prev_unclean is not None
    assert e_b._prev_unclean["pid"] == fake_pid


# ---------------------------------------------------------------------------
# M12: atexit subprocess verification (Codex review)
# ---------------------------------------------------------------------------


def test_atexit_marks_clean_exit_via_subprocess(tmp_path: Path):
    """M12: Importing piia_engram.mcp_server registers an atexit handler
    that calls _mark_clean_exit. A subprocess that imports and exits
    normally must leave session_state.json with last_clean_exit=True.

    This is the integration-level proof that the atexit plumbing works
    end-to-end in a real process lifecycle (not just unit-testing
    _mark_clean_exit in isolation).
    """
    import json
    import subprocess
    import sys

    script = (
        "import os; "
        f"os.environ['ENGRAM_DIR'] = {str(tmp_path)!r}; "
        "os.environ['ENGRAM_HEARTBEAT_INTERVAL'] = '0'; "
        "import piia_engram.mcp_server; "
        # Force the module to initialize with our tmp_path
        # (the import triggers Engram() and atexit registration)
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"Subprocess failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    state_path = tmp_path / "session_state.json"
    assert state_path.is_file(), (
        f"session_state.json not created under {tmp_path}. "
        f"Dir contents: {list(tmp_path.iterdir())}"
    )
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["last_clean_exit"] is True, (
        f"Expected last_clean_exit=True after normal subprocess exit, "
        f"got: {data}"
    )
