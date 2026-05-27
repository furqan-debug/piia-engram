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
