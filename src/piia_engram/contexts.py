"""Engram agent context auto-save — 像 Office 自动保存一样保护 AI 对话上下文。

设计原则：
- 静默记录，按需找回（行车记录仪模式）
- 按 tool 分隔，互不干扰
- 不自动恢复到新会话，不过期删除
- 文件极小（几 KB），永久保留

v3.30 additions (mechanism 5):
- ``append_daily_log`` / ``get_daily_log`` for ``~/.engram/daily/<pid>/<YYYY-MM-DD>.md``
  — human-readable per-project day log; used by wrap_up_session and the
  get_resume_brief tool to give the next session a glance-able "what
  happened today" timeline alongside the structured lessons/decisions.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .storage import _project_id

logger = logging.getLogger(__name__)


def _sanitize_tool_name(name: str) -> str:
    """Normalize tool name for filesystem use."""
    return name.strip().lower().replace(" ", "_").replace("/", "_")


class ContextStoreMixin:
    """Mixin: agent context auto-save and recovery.

    Stores conversation checkpoints per-tool in ``~/.engram/contexts/{tool}/``.
    Each session is one ``.md`` file, append-only during the session.
    """

    root: Path  # provided by Engram base class

    @property
    def _contexts_dir(self) -> Path:
        return self.root / "contexts"

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_agent_context(
        self,
        tool: str,
        content: str,
        session_id: str = "",
        project_folder: str = "",
        actions: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Save or append a context checkpoint for a tool session.

        Args:
            tool: Tool name (e.g. ``claude_code``, ``codex``, ``cursor``).
            content: Free-text checkpoint — tasks, progress, next steps.
            session_id: Reuse to append to an existing session file.
                        If empty, a new session file is created.
            project_folder: Optional project path (written in the header).
            actions: Optional structured action log — list of dicts with
                     ``tool_called``, ``arguments_summary``, ``result_summary``.
                     Used by playbook auto-extraction for higher-fidelity steps.

        Returns:
            ``{session_id, file, tool, appended}``
        """
        tool_safe = _sanitize_tool_name(tool)
        tool_dir = self._contexts_dir / tool_safe
        tool_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()

        if not session_id:
            session_id = now.strftime("%Y-%m-%dT%H-%M-%S")

        file_path = tool_dir / f"{session_id}.md"
        timestamp = now.strftime("%H:%M")
        appended = file_path.exists()

        # Build checkpoint body
        body = content
        if actions:
            body += "\n\n#### Actions\n"
            for i, act in enumerate(actions, 1):
                tool_called = act.get("tool_called", "")
                args_summary = act.get("arguments_summary", "")
                result_summary = act.get("result_summary", "")
                body += f"{i}. `{tool_called}`"
                if args_summary:
                    body += f" — {args_summary}"
                if result_summary:
                    body += f" → {result_summary}"
                body += "\n"

        if appended:
            existing = file_path.read_text(encoding="utf-8")
            entry = f"\n### {timestamp}\n{body}\n"
            file_path.write_text(existing + entry, encoding="utf-8")
        else:
            header = f"# Session: {tool} @ {now.strftime('%Y-%m-%d %H:%M')}\n"
            if project_folder:
                header += f"## Project: {project_folder}\n"
            header += f"\n### {timestamp}\n{body}\n"
            file_path.write_text(header, encoding="utf-8")

        return {
            "session_id": session_id,
            "file": str(file_path),
            "tool": tool_safe,
            "appended": appended,
        }

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_recent_context(
        self,
        tool: str = "",
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        """Return the most recent context sessions.

        Args:
            tool: Tool name.  If empty, searches **all** tools.
            limit: Max sessions to return (default 1 = latest only).

        Returns:
            List of ``{tool, session_id, content, modified_at}`` dicts,
            sorted newest-first.
        """
        results: list[dict[str, Any]] = []

        if tool:
            tool_names = [_sanitize_tool_name(tool)]
        else:
            if not self._contexts_dir.exists():
                return []
            tool_names = [
                d.name for d in self._contexts_dir.iterdir() if d.is_dir()
            ]

        for t in tool_names:
            tool_dir = self._contexts_dir / t
            if not tool_dir.exists():
                continue
            files = sorted(
                tool_dir.glob("*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for f in files[:limit]:
                results.append({
                    "tool": t,
                    "session_id": f.stem,
                    "content": f.read_text(encoding="utf-8"),
                    "modified_at": datetime.fromtimestamp(
                        f.stat().st_mtime,
                    ).replace(microsecond=0).isoformat(),
                })

        results.sort(key=lambda x: x["modified_at"], reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_agent_sessions(
        self,
        tool: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List available context sessions (metadata only, no content).

        Args:
            tool: Tool name.  If empty, lists **all** tools.
            limit: Max sessions to return.

        Returns:
            List of ``{tool, session_id, modified_at, size_bytes}`` dicts,
            sorted newest-first.
        """
        results: list[dict[str, Any]] = []

        if tool:
            tool_names = [_sanitize_tool_name(tool)]
        else:
            if not self._contexts_dir.exists():
                return []
            tool_names = [
                d.name for d in self._contexts_dir.iterdir() if d.is_dir()
            ]

        for t in tool_names:
            tool_dir = self._contexts_dir / t
            if not tool_dir.exists():
                continue
            files = sorted(
                tool_dir.glob("*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for f in files:
                results.append({
                    "tool": t,
                    "session_id": f.stem,
                    "modified_at": datetime.fromtimestamp(
                        f.stat().st_mtime,
                    ).replace(microsecond=0).isoformat(),
                    "size_bytes": f.stat().st_size,
                })

        results.sort(key=lambda x: x["modified_at"], reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------
    # Daily log (v3.30 mechanism 5)
    # ------------------------------------------------------------------

    @property
    def _daily_dir(self) -> Path:
        """Root directory for per-project daily logs."""
        return self.root / "daily"

    def _daily_log_path(self, project_folder: str, date: str | None = None) -> Path:
        """Return the .md path for a project's daily log on the given date."""
        if not project_folder:
            project_folder = "(no-project)"
        pid = _project_id(project_folder)
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        return self._daily_dir / pid / f"{date}.md"

    def append_daily_log(
        self,
        project_folder: str,
        content: str,
        event_type: str = "session",
        source_tool: str = "",
    ) -> dict[str, Any]:
        """Append a timestamped entry to today's daily log for a project.

        Designed to be cheap and lossy-safe: a single append-only markdown
        file per (project, day). Used by ``wrap_up_session`` for the
        session-end summary; can also be called manually from the AI to
        leave a "marker" comment in the day's audit trail.

        Args:
            project_folder: Project folder path. If empty, logs under a
                synthetic ``(no-project)`` bucket so no entry is lost.
            content: Free-text entry body. Will be appended verbatim.
            event_type: Short tag rendered in the header — e.g. ``session``,
                ``lesson``, ``decision``, ``checkpoint``, ``manual``.
            source_tool: Optional originating tool name (e.g. ``claude_code``).

        Returns:
            ``{file, project_folder, event_type, created}`` where ``created``
            indicates whether a new daily file was created (vs appended to).
        """
        path = self._daily_log_path(project_folder)
        path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        timestamp = now.strftime("%H:%M:%S")
        created = not path.exists()

        if created:
            date_header = now.strftime("%Y-%m-%d")
            header = [
                f"# Daily Log · {date_header}",
                "",
                f"**Project**: {project_folder or '(no-project)'}",
                "",
            ]
            path.write_text("\n".join(header) + "\n", encoding="utf-8")

        tag = event_type.strip() or "event"
        src = f" · {source_tool.strip()}" if source_tool.strip() else ""
        entry = f"## {timestamp}  [{tag}]{src}\n\n{content.rstrip()}\n\n"

        with path.open("a", encoding="utf-8") as f:
            f.write(entry)

        return {
            "file": str(path),
            "project_folder": project_folder,
            "event_type": tag,
            "created": created,
        }

    def get_daily_log(
        self,
        project_folder: str,
        date: str | None = None,
    ) -> dict[str, Any]:
        """Return a project's daily log for the requested date (default today).

        Returns ``{file, date, exists, content}``. ``content`` is empty
        string when no log exists yet (not an error).
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        path = self._daily_log_path(project_folder, date=date)
        exists = path.is_file()
        return {
            "file": str(path),
            "date": date,
            "exists": exists,
            "content": path.read_text(encoding="utf-8") if exists else "",
        }

    # ------------------------------------------------------------------
    # Resume brief (v3.30 mechanism 3)
    # ------------------------------------------------------------------

    # File names this brief will surface to the AI as "things you should
    # read next". Order matters — the first existing one is most important.
    _RESUME_DOC_CANDIDATES: tuple[str, ...] = (
        "PROJECT_REGISTRY.md",
        "CLAUDE.md",
        "AGENTS.md",
        "CHANGELOG.md",
        "README.md",
        "README.zh-CN.md",
    )

    def get_resume_brief(
        self,
        project_folder: str = "",
        token_budget: int = 2000,
    ) -> dict[str, Any]:
        """Return a ready-to-paste resume brief for a cross-session / cross-tool restart.

        v3.30 mechanism (3). This is the "what does the next AI need to know
        in 30 seconds" entry point. The output bundles:

        - User identity (role, language, work patterns)
        - Project snapshot (version, tech stack, known issues)
        - Today's daily log entries (if any) — short timeline
        - Last 1–2 recent context sessions (cross-tool, newest first)
        - Top 3 verified lessons and decisions for the project's domain
        - Suggested docs the AI should read next (filesystem-checked)

        Output is wrapped in ``<engram-resume priority="high">`` tags so
        client AIs (Claude Code via additionalContext, Codex via system
        prompt, etc.) treat it as authoritative.

        Args:
            project_folder: Path used to pick the project snapshot, daily
                log, and doc-candidates. May be empty — in that case the
                brief is identity-only.
            token_budget: Soft cap on output length, ~4 chars/token. Body
                is truncated section-by-section in priority order to fit.

        Returns:
            ``{markdown, sections_included, sections_skipped, byte_size,
            estimated_tokens, project_folder, suggested_docs}``.
        """
        char_budget = max(400, int(token_budget) * 4)

        sections: list[tuple[str, str]] = []
        sections_skipped: list[str] = []

        # ---- 1. Identity (cheapest, always include) ---------------------
        try:
            profile = self.get_profile() if hasattr(self, "get_profile") else {}
        except Exception:
            profile = {}
        identity_lines = ["## Who you are working with"]
        for key in ("role", "language", "technical_level"):
            v = profile.get(key) if isinstance(profile, dict) else None
            if v:
                identity_lines.append(f"- **{key}**: {v}")
        try:
            prefs = self.get_preferences() if hasattr(self, "get_preferences") else {}
            wp = prefs.get("work_patterns") if isinstance(prefs, dict) else None
            if isinstance(wp, dict) and wp:
                identity_lines.append("- **work_patterns**:")
                for k, val in list(wp.items())[:6]:
                    identity_lines.append(f"  - {k}: {val}")
        except Exception:
            pass
        sections.append(("identity", "\n".join(identity_lines)))

        # ---- 2. Project snapshot ----------------------------------------
        suggested_docs: list[str] = []
        if project_folder and hasattr(self, "get_project_snapshot"):
            try:
                snap = self.get_project_snapshot(project_folder)
                if isinstance(snap, dict) and snap:
                    proj_lines = ["## Current project"]
                    proj_lines.append(f"- **folder**: {project_folder}")
                    for key in ("title", "version", "test_count",
                                "mcp_tool_definitions", "module_count"):
                        if snap.get(key) is not None:
                            proj_lines.append(f"- **{key}**: {snap[key]}")
                    ts = snap.get("tech_stack")
                    if isinstance(ts, list) and ts:
                        proj_lines.append(f"- **tech_stack**: {', '.join(ts)}")
                    issues = snap.get("known_issues")
                    if isinstance(issues, list) and issues:
                        proj_lines.append("- **known_issues**:")
                        for it in issues[:5]:
                            proj_lines.append(f"  - {it}")
                    if snap.get("notes"):
                        notes_text = str(snap["notes"])[:300]
                        proj_lines.append(f"- **notes**: {notes_text}")
                    sections.append(("project_snapshot", "\n".join(proj_lines)))
                else:
                    sections_skipped.append("project_snapshot (empty)")
            except Exception as exc:
                sections_skipped.append(f"project_snapshot ({exc})")

            # Doc candidates that actually exist on disk.
            try:
                root = Path(project_folder)
                if root.is_dir():
                    for fname in self._RESUME_DOC_CANDIDATES:
                        if (root / fname).is_file():
                            suggested_docs.append(fname)
            except Exception:
                pass

        # ---- 3. Today's daily log (if project given) --------------------
        if project_folder:
            try:
                daily = self.get_daily_log(project_folder)
                if daily["exists"] and daily["content"].strip():
                    # Keep only the most recent few entries (last ~1500 chars).
                    body = daily["content"]
                    if len(body) > 1500:
                        body = "…(earlier entries truncated)…\n" + body[-1500:]
                    sections.append((
                        "daily_log",
                        f"## Today's daily log ({daily['date']})\n\n{body}",
                    ))
            except Exception as exc:
                sections_skipped.append(f"daily_log ({exc})")

        # ---- 4. Recent agent contexts (cross-tool) ---------------------
        try:
            recent = self.get_recent_context(limit=2)
            if recent:
                ctx_lines = ["## Recent session contexts (newest first)"]
                for r in recent:
                    body = r.get("content", "")
                    if len(body) > 600:
                        body = body[:600].rstrip() + "…"
                    ctx_lines.append(
                        f"### {r.get('tool', '?')} @ {r.get('modified_at', '')}"
                    )
                    ctx_lines.append(body)
                sections.append(("recent_context", "\n\n".join(ctx_lines)))
        except Exception as exc:
            sections_skipped.append(f"recent_context ({exc})")

        # ---- 5. Top lessons + decisions --------------------------------
        try:
            if hasattr(self, "get_lessons"):
                lessons = self.get_lessons(limit=3, _update_access=False)
                if lessons:
                    parts = ["## Recent verified lessons"]
                    for L in lessons:
                        if L.get("status") != "active":
                            continue
                        if L.get("tier") and L.get("tier") != "verified":
                            continue
                        summary = (L.get("summary") or "").strip()
                        if summary:
                            parts.append(f"- {summary}")
                    if len(parts) > 1:
                        sections.append(("lessons", "\n".join(parts)))
        except Exception as exc:
            sections_skipped.append(f"lessons ({exc})")

        try:
            if hasattr(self, "get_decisions"):
                decs = self.get_decisions(limit=3, _update_access=False)
                if decs:
                    parts = ["## Recent verified decisions"]
                    for D in decs:
                        if D.get("status") != "active":
                            continue
                        if D.get("tier") and D.get("tier") != "verified":
                            continue
                        q = (D.get("question") or D.get("title") or "").strip()
                        c = (D.get("choice") or "").strip()
                        if q and c:
                            parts.append(f"- **{q}** → {c}")
                        elif q:
                            parts.append(f"- {q}")
                    if len(parts) > 1:
                        sections.append(("decisions", "\n".join(parts)))
        except Exception as exc:
            sections_skipped.append(f"decisions ({exc})")

        # ---- 6. Suggested next reads (doc paths) -----------------------
        if suggested_docs:
            doc_lines = ["## Suggested docs to read next"]
            doc_lines.append(
                "These project files exist and likely contain useful context "
                "for what we are doing. Read them before asking the user "
                "for context that's already documented."
            )
            for fname in suggested_docs:
                doc_lines.append(f"- {fname}")
            sections.append(("suggested_docs", "\n".join(doc_lines)))

        # ---- Assemble with token budget --------------------------------
        # Priority: identity > project_snapshot > daily_log > recent_context
        #           > lessons > decisions > suggested_docs
        priority = [
            "identity",
            "project_snapshot",
            "daily_log",
            "recent_context",
            "lessons",
            "decisions",
            "suggested_docs",
        ]
        by_name = {name: text for name, text in sections}
        included: list[str] = []
        parts: list[str] = []
        total = 0
        for name in priority:
            text = by_name.get(name)
            if not text:
                continue
            text_len = len(text) + 2  # for newlines between sections
            if total + text_len > char_budget and parts:
                sections_skipped.append(f"{name} (budget)")
                continue
            parts.append(text)
            included.append(name)
            total += text_len

        body = "\n\n".join(parts)
        # Wrap in XML so Claude prioritizes (matches ContextStream's
        # observed effective pattern for additionalContext injection).
        markdown = (
            "<engram-resume priority=\"high\">\n"
            "Engram resume brief — use this as authoritative context for "
            "this session before asking the user to re-explain anything.\n\n"
            + body
            + "\n</engram-resume>"
        )

        # ~4 chars/token is the standard rough estimate.
        est_tokens = max(1, len(markdown) // 4)

        return {
            "markdown": markdown,
            "sections_included": included,
            "sections_skipped": sections_skipped,
            "byte_size": len(markdown.encode("utf-8")),
            "estimated_tokens": est_tokens,
            "project_folder": project_folder,
            "suggested_docs": suggested_docs,
        }
