from __future__ import annotations

import inspect
import json
import logging
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable


REPO = Path("E:/Personal Intelligence Identity Asset/engram")
SRC = REPO / "src"
AUDIT_DIR = REPO / "experiments" / "memory_audit"
SCRIPTS_DIR = AUDIT_DIR / "scripts"
RESULTS_DIR = AUDIT_DIR / "results"

for path in (AUDIT_DIR, SCRIPTS_DIR, RESULTS_DIR):
    path.mkdir(parents=True, exist_ok=True)

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from piia_engram.core import Engram  # noqa: E402
from piia_engram.storage import _read_json, _write_json  # noqa: E402

logging.getLogger("piia_engram").setLevel(logging.ERROR)
logging.getLogger("piia_engram.core").setLevel(logging.ERROR)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def has_method(obj: Any, name: str) -> bool:
    return callable(getattr(obj, name, None))


def signature_text(obj: Any, name: str) -> str:
    attr = getattr(obj, name, None)
    if not callable(attr):
        return "MISSING"
    try:
        return str(inspect.signature(attr))
    except (TypeError, ValueError):
        return "SIGNATURE_UNAVAILABLE"


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_search(result: dict) -> list[dict]:
    items: list[dict] = []
    for kind in ("lessons", "decisions", "playbooks"):
        for item in result.get(kind, []) or []:
            view = dict(item)
            view["_type"] = kind[:-1] if kind.endswith("s") else kind
            items.append(view)
    return items


def text_of(item: dict) -> str:
    return " ".join(
        str(item.get(key, ""))
        for key in (
            "summary",
            "detail",
            "title",
            "question",
            "choice",
            "reasoning",
            "domain",
            "source_tool",
            "name",
        )
    )


def contains_text(item: dict, needle: str) -> bool:
    return needle.lower() in text_of(item).lower()


def find_lesson_by_summary(eng: Engram, summary: str) -> dict | None:
    for lesson in eng.get_lessons(limit=None, _update_access=False):
        if lesson.get("summary") == summary:
            return lesson
    return None


def find_decision_by_question(eng: Engram, question: str, choice: str = "") -> dict | None:
    for decision in eng.get_decisions(limit=None, _update_access=False):
        title = decision.get("question") or decision.get("title") or ""
        if title == question and (not choice or decision.get("choice") == choice):
            return decision
    return None


def find_playbook_by_title(eng: Engram, title: str) -> dict | None:
    for playbook in eng.get_playbooks(limit=None, _update_access=False):
        if playbook.get("title") == title:
            return playbook
    return None


def ensure_lesson(
    eng: Engram,
    summary: str,
    domain: str = "",
    source_tool: str = "codex",
    detail: str = "",
    **extra: Any,
) -> dict:
    result = eng.add_lesson(summary, domain=domain, source_tool=source_tool, detail=detail, **extra)
    if result.get("status") == "duplicate":
        existing = find_lesson_by_summary(eng, summary)
        if existing:
            return {**existing, "_action": "duplicate_reused"}
        existing_id = result.get("existing_id")
        if existing_id:
            for lesson in eng.get_lessons(limit=None, _update_access=False):
                if lesson.get("id") == existing_id:
                    return {**lesson, "_action": "duplicate_reused"}
    return result


def ensure_decision(
    eng: Engram,
    question: str,
    choice: str,
    reasoning: str = "",
    domain: str = "",
    source_tool: str = "codex",
    **extra: Any,
) -> dict:
    result = eng.add_decision(
        question,
        choice=choice,
        reasoning=reasoning,
        source_tool=source_tool,
        domain=domain,
        **extra,
    )
    if result.get("status") == "duplicate":
        existing = find_decision_by_question(eng, question, choice)
        if existing:
            return {**existing, "_action": "duplicate_reused"}
        existing_id = result.get("existing_id")
        if existing_id:
            for decision in eng.get_decisions(limit=None, _update_access=False):
                if decision.get("id") == existing_id:
                    return {**decision, "_action": "duplicate_reused"}
    return result


def ensure_playbook(
    eng: Engram,
    title: str,
    steps: list[dict],
    domain: str = "",
    source_tool: str = "codex",
    triggers: list[str] | None = None,
    **extra: Any,
) -> dict:
    payload = {
        "title": title,
        "triggers": triggers or [],
        "steps": steps,
        "domain": domain,
        "source_tool": source_tool,
        **extra,
    }
    result = eng.add_playbook(payload, source_tool=source_tool)
    if result.get("status") == "duplicate":
        existing = find_playbook_by_title(eng, title)
        if existing:
            return {**existing, "_action": "duplicate_reused"}
        existing_id = result.get("existing_id")
        if existing_id:
            pb = eng.get_playbook(existing_id, _update_access=False)
            if not pb.get("error"):
                return {**pb, "_action": "duplicate_reused"}
    return result


def set_lesson_last_reviewed(eng: Engram, lesson_id: str, days_ago: int) -> dict:
    path = eng._knowledge_dir / "lessons.json"
    lessons = _read_json(path)
    if not isinstance(lessons, list):
        return {"error": "lessons.json is not a list"}
    target = None
    for lesson in lessons:
        if lesson.get("id") == lesson_id:
            target = lesson
            break
    if not target:
        return {"error": f"lesson not found: {lesson_id}"}
    ts = (datetime.now() - timedelta(days=days_ago)).replace(microsecond=0).isoformat()
    target["last_reviewed"] = ts
    target.setdefault("access_count", 0)
    _write_json(path, lessons)
    return {"id": lesson_id, "last_reviewed": ts}


def wrap_up_like_session(
    eng: Engram,
    summary: str,
    project_folder: str,
    source_tool: str = "codex",
) -> dict:
    """Core-level equivalent for the MCP-only wrap_up_session tool."""
    insights = eng.extract_session_insights(summary, source_tool=source_tool)
    context = eng.save_agent_context(
        tool=source_tool,
        content=summary,
        project_folder=project_folder,
        actions=[
            {
                "tool_called": "wrap_up_like_session",
                "arguments_summary": "core API fallback for MCP wrap_up_session",
                "result_summary": "insights extracted and context saved",
            }
        ],
    )
    eng.save_project_snapshot(
        project_folder,
        {
            "title": "Engram memory audit",
            "tech_stack": ["python", "mcp", "engram"],
            "known_issues": ["codex_unit_test_marker"],
            "notes": summary,
            "last_codex_audit": now_iso(),
        },
    )
    tiers = eng.evaluate_tiers() if has_method(eng, "evaluate_tiers") else {"skipped": True}
    return {"insights": insights, "context": context, "tiers": tiers}


class CaseRecorder:
    def __init__(self, label: str, expected_total: int | None = None) -> None:
        self.label = label
        self.expected_total = expected_total
        self.results: list[dict[str, Any]] = []
        self.pass_count = 0
        self.fail_count = 0
        self.skip_count = 0

    def case(self, name: str, func: Callable[[], tuple[bool, str, Any]]) -> None:
        try:
            ok, detail, data = func()
            status = "PASS" if ok else "FAIL"
            if ok:
                self.pass_count += 1
            else:
                self.fail_count += 1
            self.results.append({"name": name, "status": status, "detail": str(detail), "data": data})
            print(f"  [{status}] {name}: {str(detail)[:180]}")
        except Exception as exc:  # keep every case isolated
            self.fail_count += 1
            detail = f"EXCEPTION: {exc}"
            self.results.append({"name": name, "status": "FAIL", "detail": detail, "data": None})
            print(f"  [FAIL] {name}: {detail}")
            traceback.print_exc()

    def skip(self, name: str, detail: str, data: Any = None) -> None:
        self.skip_count += 1
        self.results.append({"name": name, "status": "SKIP", "detail": detail, "data": data})
        print(f"  [SKIP] {name}: {detail[:180]}")

    @property
    def total(self) -> int:
        return self.pass_count + self.fail_count + self.skip_count

    def summary(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "expected_total": self.expected_total,
            "pass": self.pass_count,
            "fail": self.fail_count,
            "skip": self.skip_count,
            "total": self.total,
            "results": self.results,
        }

    def print_summary(self) -> None:
        expected = f" / expected {self.expected_total}" if self.expected_total is not None else ""
        print("=" * 60)
        print(
            f"{self.label}: {self.pass_count} PASS / {self.fail_count} FAIL / "
            f"{self.skip_count} SKIP / {self.total} TOTAL{expected}"
        )


def status_table(results: list[dict[str, Any]]) -> str:
    lines = ["| Case | 结果 | 备注 |", "|------|------|------|"]
    for item in results:
        detail = str(item.get("detail", "")).replace("\n", " ")[:240]
        lines.append(f"| {item.get('name', '')} | {item.get('status', '')} | {detail} |")
    return "\n".join(lines)
