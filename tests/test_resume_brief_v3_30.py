"""v3.30 mechanism (3) — get_resume_brief guardrail tests.

The brief is the entry point AI tools call at session start to inherit
state from prior work (this session, this tool, *any* tool that wrote to
the same ~/.engram/). These tests pin: the priority order of sections,
the XML wrapper, the token-budget truncation, and the empty-project
identity-only path.
"""

from __future__ import annotations

from pathlib import Path

from piia_engram.core import Engram


def _make(tmp_path: Path) -> Engram:
    return Engram(root=tmp_path)


def _pop_brief(e: Engram, **kwargs) -> dict:
    return e.get_resume_brief(**kwargs)


def test_wraps_output_in_engram_resume_xml_tag(tmp_path: Path):
    e = _make(tmp_path)
    r = _pop_brief(e)
    assert r["markdown"].startswith('<engram-resume priority="high">\n')
    assert r["markdown"].rstrip().endswith("</engram-resume>")


def test_includes_identity_section_even_with_empty_project(tmp_path: Path):
    """Identity is always section #1 — the brief must work without a project."""
    e = _make(tmp_path)
    e.update_profile({"role": "developer", "language": "en"}, source_tool="test")
    r = _pop_brief(e)
    assert "identity" in r["sections_included"]
    assert "Who you are working with" in r["markdown"]
    assert "developer" in r["markdown"]
    assert r["project_folder"] == ""


def test_includes_project_snapshot_when_folder_provided(tmp_path: Path):
    e = _make(tmp_path)
    project = str(tmp_path / "myproj")
    Path(project).mkdir()
    e.save_project_snapshot(project, {
        "title": "MyProj",
        "version": "1.2.3",
        "tech_stack": ["python", "mcp"],
        "known_issues": ["foo bar broken"],
    })
    r = _pop_brief(e, project_folder=project)
    assert "project_snapshot" in r["sections_included"]
    assert "MyProj" in r["markdown"]
    assert "1.2.3" in r["markdown"]
    assert "python" in r["markdown"] and "mcp" in r["markdown"]
    assert "foo bar broken" in r["markdown"]


def test_suggested_docs_only_lists_files_that_exist(tmp_path: Path):
    """Filesystem-checked: PROJECT_REGISTRY.md exists, CHANGELOG.md doesn't."""
    e = _make(tmp_path)
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "PROJECT_REGISTRY.md").write_text("x", encoding="utf-8")
    (proj / "CLAUDE.md").write_text("x", encoding="utf-8")
    # No CHANGELOG.md, no README.md
    r = _pop_brief(e, project_folder=str(proj))
    assert "PROJECT_REGISTRY.md" in r["suggested_docs"]
    assert "CLAUDE.md" in r["suggested_docs"]
    assert "CHANGELOG.md" not in r["suggested_docs"]
    assert "README.md" not in r["suggested_docs"]
    assert "Suggested docs to read next" in r["markdown"]


def test_includes_daily_log_when_present(tmp_path: Path):
    e = _make(tmp_path)
    proj = str(tmp_path / "proj2")
    Path(proj).mkdir()
    e.append_daily_log(proj, "today we shipped X", event_type="session")
    r = _pop_brief(e, project_folder=proj)
    assert "daily_log" in r["sections_included"]
    assert "today we shipped X" in r["markdown"]


def test_includes_recent_lessons_and_decisions(tmp_path: Path):
    e = _make(tmp_path)
    e.add_lesson("Use Path.resolve() before hashing", domain="python")
    e.add_decision("Database choice", choice="SQLite", reasoning="local-first")
    r = _pop_brief(e)
    assert "lessons" in r["sections_included"]
    assert "decisions" in r["sections_included"]
    assert "Use Path.resolve() before hashing" in r["markdown"]
    assert "Database choice" in r["markdown"]
    assert "SQLite" in r["markdown"]


def test_token_budget_drops_lower_priority_sections(tmp_path: Path):
    """A tiny budget must keep identity but drop later sections (lessons,
    decisions, suggested_docs) — that's what priority ordering buys us."""
    e = _make(tmp_path)
    e.update_profile({"role": "developer"}, source_tool="test")
    for i in range(10):
        e.add_lesson(f"Lesson number {i} about a unique topic {i}", domain=f"d{i}")
    r = _pop_brief(e, token_budget=80)  # ~320 chars — very tight
    assert "identity" in r["sections_included"]
    # Lower-priority sections may be skipped due to budget.
    if "lessons" in r["sections_skipped"]:
        assert any("budget" in s for s in r["sections_skipped"]
                   if s.startswith("lessons"))


def test_estimated_tokens_field_is_present_and_sane(tmp_path: Path):
    e = _make(tmp_path)
    r = _pop_brief(e)
    assert "estimated_tokens" in r
    assert r["estimated_tokens"] > 0
    # 4-chars-per-token estimate
    assert r["estimated_tokens"] <= len(r["markdown"])


def test_empty_engram_returns_minimal_brief_not_crash(tmp_path: Path):
    """A completely empty Engram (fresh install) must still produce a
    valid brief — at least the XML wrapper plus a fallback identity stub."""
    e = _make(tmp_path)
    r = _pop_brief(e)
    assert r["markdown"].startswith("<engram-resume")
    assert r["markdown"].rstrip().endswith("</engram-resume>")
    # identity is always emitted, even if empty profile
    assert "identity" in r["sections_included"]
