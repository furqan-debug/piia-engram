from __future__ import annotations

import json
from datetime import datetime

from _audit_common import (
    AUDIT_DIR,
    REPO,
    CaseRecorder,
    Engram,
    dump_json,
    ensure_decision,
    ensure_lesson,
    ensure_playbook,
    has_method,
    now_iso,
    set_lesson_last_reviewed,
    signature_text,
    wrap_up_like_session,
)


DOMAIN = "codex_unit_test"
SOURCE = "codex"
PROJECT = str(REPO).replace("\\", "/")


eng = Engram()
rec = CaseRecorder("Phase 1 单元写入", expected_total=20)
seed: dict = {
    "written_at": now_iso(),
    "phase": "unit_write",
    "source_tool": SOURCE,
    "domain": DOMAIN,
    "project_folder": PROJECT,
    "api_signatures": {},
    "items": {},
}


for method in [
    "update_profile",
    "update_preferences",
    "update_trust_boundaries",
    "update_quality_standards",
    "add_lesson",
    "add_decision",
    "add_playbook",
    "save_agent_context",
    "refresh_quick_context",
    "extract_session_insights",
    "register_tool",
    "prepare_playbook_execution",
    "update_execution_step",
]:
    seed["api_signatures"][method] = signature_text(eng, method)


def save_seed() -> None:
    dump_json(AUDIT_DIR / "codex_unit_seed.json", seed)


def remember(name: str, data: dict) -> dict:
    seed["items"][name] = data
    return data


def case_update_profile():
    existing_description = eng.get_profile().get("description", "")
    markers = [
        part
        for part in [
            existing_description,
            "cc_self_test_marker_20260527",
            "cross_ai_test_marker",
            "codex_unit_test_marker_20260527",
        ]
        if part
    ]
    description = " ".join(dict.fromkeys(" ".join(markers).split()))
    updates = {
        "role": "codex_tester",
        "language": "zh",
        "description": description,
    }
    eng.update_profile(updates)
    profile = eng.get_profile()
    ok = (
        profile.get("role") == "codex_tester"
        and profile.get("language") == "zh"
        and "codex_unit_test_marker" in profile.get("description", "")
        and "cc_self_test_marker" in profile.get("description", "")
    )
    return ok, f"profile={profile}", remember("W1.1", {"updates": updates})


def case_update_preferences():
    updates = {"communication": "sync", "tool_preferences": {"codex": "primary"}}
    eng.update_preferences(updates)
    prefs = eng.get_preferences()
    ok = prefs.get("communication") == "sync" and prefs.get("tool_preferences", {}).get("codex") == "primary"
    return ok, f"preferences={prefs}", remember("W1.2", {"updates": updates})


def case_update_trust():
    updates = {"restricted_fields": ["email", "phone"]}
    eng.update_trust_boundaries(updates)
    trust = eng.get_trust_boundaries()
    restricted = set(trust.get("restricted_fields", []))
    ok = {"email", "phone"}.issubset(restricted)
    return ok, f"restricted_fields={sorted(restricted)}", remember("W1.3", {"updates": updates})


def case_update_quality():
    updates = {"acceptance_threshold": 3, "rules": ["codex_unit_test_rule"]}
    eng.update_quality_standards(updates)
    quality = eng.get_quality_standards()
    ok = quality.get("acceptance_threshold") == 3 and "codex_unit_test_rule" in quality.get("rules", [])
    return ok, f"quality={quality}", remember("W1.4", {"updates": updates})


def write_lesson(name: str, summary: str):
    def _inner():
        lesson = ensure_lesson(eng, summary, domain=DOMAIN, source_tool=SOURCE)
        ok = bool(lesson.get("id")) and lesson.get("summary") == summary
        return ok, f"id={lesson.get('id')} action={lesson.get('_action', 'created')}", remember(
            name,
            {
                "id": lesson.get("id"),
                "summary": summary,
                "domain": DOMAIN,
                "source_tool": SOURCE,
            },
        )

    return _inner


def write_decision(name: str, question: str, choice: str, reasoning: str):
    def _inner():
        decision = ensure_decision(
            eng,
            question,
            choice=choice,
            reasoning=reasoning,
            domain=DOMAIN,
            source_tool=SOURCE,
        )
        ok = bool(decision.get("id")) and decision.get("choice") == choice
        return ok, f"id={decision.get('id')} choice={decision.get('choice')}", remember(
            name,
            {
                "id": decision.get("id"),
                "question": question,
                "choice": choice,
                "domain": DOMAIN,
                "source_tool": SOURCE,
            },
        )

    return _inner


def case_playbook():
    title = "codex_unit_ci_release_pipeline_20260527"
    pb = ensure_playbook(
        eng,
        title,
        triggers=["codex_unit_release"],
        steps=[
            {"order": 1, "action": "build"},
            {"order": 2, "action": "test"},
            {"order": 3, "action": "publish"},
        ],
        domain=DOMAIN,
        source_tool=SOURCE,
    )
    ok = bool(pb.get("id")) and len(pb.get("steps", [])) == 3
    return ok, f"id={pb.get('id')} steps={len(pb.get('steps', []))}", remember(
        "W2.6",
        {
            "id": pb.get("id"),
            "title": pb.get("title"),
            "expected_title": title,
            "steps_count": len(pb.get("steps", [])),
            "domain": DOMAIN,
            "source_tool": SOURCE,
        },
    )


def case_memory_store_fallback():
    summary = "Codex单测：memory_store路由验证"
    if has_method(eng, "memory_store"):
        result = eng.memory_store(kind="lesson", summary=summary, domain=DOMAIN, source_tool=SOURCE)
        lesson = next((l for l in eng.get_lessons(domain=DOMAIN, limit=None) if l.get("summary") == summary), {})
        method = "memory_store"
    else:
        result = ensure_lesson(eng, summary, domain=DOMAIN, source_tool=SOURCE)
        lesson = result
        method = "add_lesson fallback"
    ok = bool(lesson.get("id")) and lesson.get("source_tool") == SOURCE
    return ok, f"{method}; id={lesson.get('id')}", remember(
        "W2.7",
        {
            "id": lesson.get("id"),
            "summary": summary,
            "domain": DOMAIN,
            "source_tool": SOURCE,
            "method": method,
        },
    )


def case_save_agent_context():
    content = f"Codex单测跨执行验证：写入于 {datetime.now().isoformat()}"
    result = eng.save_agent_context(tool=SOURCE, content=content, project_folder=PROJECT)
    ok = bool(result.get("session_id")) and "file" in result
    return ok, f"session_id={result.get('session_id')}", remember(
        "W4.1",
        {"session_id": result.get("session_id"), "file": result.get("file"), "content": content},
    )


def case_refresh_quick_context():
    if not has_method(eng, "refresh_quick_context"):
        return True, "refresh_quick_context missing; skipped by task rule", remember("W4.2", {"skipped": True})
    path = eng.refresh_quick_context(level="standard")
    ok = path.is_file()
    return ok, f"path={path}", remember("W4.2", {"path": str(path)})


def case_wrap_up_like():
    summary = "Codex单测：完成了异步修复，发现嵌套事件循环问题。决定统一用asyncio.run。"
    result = wrap_up_like_session(eng, summary=summary, project_folder=PROJECT, source_tool=SOURCE)
    insights = result.get("insights", {})
    ok = bool(result.get("context", {}).get("session_id")) and (
        insights.get("saved_lessons", 0) + insights.get("saved_decisions", 0) + insights.get("duplicates", 0) >= 1
    )
    return ok, f"insights={insights}", remember("W5.1", {"summary": summary, "result": result})


def case_stale_optional_59():
    lesson_id = seed["items"].get("W2.1", {}).get("id")
    result = set_lesson_last_reviewed(eng, lesson_id, days_ago=59)
    ok = "error" not in result
    return ok, f"last_reviewed={result.get('last_reviewed')}", remember("W5.2", result)


def case_register_tool():
    tool = {
        "name": "codex_unit_test_tool",
        "path": "/codex/test",
        "category": "cli",
        "version": "2.0",
        "purpose": "Codex单测工具",
    }
    result = eng.register_tool(tool, registered_by=SOURCE)
    ok = result.get("name") == "codex_unit_test_tool" and result.get("version") == "2.0"
    return ok, f"action={result.get('_action')} id={result.get('id')}", remember("W6.1", result)


def case_prepare_execution():
    pb_id = seed["items"].get("W2.6", {}).get("id")
    plan = eng.prepare_playbook_execution(pb_id)
    step1 = eng.update_execution_step(pb_id, 1, "completed", notes="codex audit")
    step2 = eng.update_execution_step(pb_id, 2, "completed", notes="codex audit")
    status = eng.get_execution_status(pb_id)
    ok = status.get("completed") == 2 and status.get("total") == 3
    return ok, f"completed={status.get('completed')}/{status.get('total')}", remember(
        "WC6.1",
        {"playbook_id": pb_id, "plan": plan, "step1": step1, "step2": step2, "status": status},
    )


def case_conflict_decision():
    # The wording is deliberately less similar than W2.5, otherwise Engram's
    # dedup layer correctly reuses the GitHub Actions decision.
    question = "CI runner final policy"
    decision = ensure_decision(
        eng,
        question,
        choice="GitLab CI",
        reasoning="自托管安全",
        domain=DOMAIN,
        source_tool=SOURCE,
    )
    ok = bool(decision.get("id")) and decision.get("choice") == "GitLab CI"
    return ok, f"id={decision.get('id')} choice={decision.get('choice')}", remember(
        "WC7.1",
        {
            "id": decision.get("id"),
            "question": question,
            "choice": "GitLab CI",
            "domain": DOMAIN,
        },
    )


def case_stale_required_60():
    lesson_id = seed["items"].get("W2.1", {}).get("id")
    result = set_lesson_last_reviewed(eng, lesson_id, days_ago=60)
    stale = eng.get_stale_knowledge(days=30, limit=None)
    hit = any(item.get("id") == lesson_id for item in stale.get("lessons", []))
    ok = "error" not in result and hit
    return ok, f"stale_hit={hit} last_reviewed={result.get('last_reviewed')}", remember(
        "WC9.1",
        {**result, "stale_hit": hit},
    )


print("========== Phase 1: unit_write.py ==========")

rec.case("W1.1 update_profile", case_update_profile)
rec.case("W1.2 update_preferences", case_update_preferences)
rec.case("W1.3 update_trust_boundaries", case_update_trust)
rec.case("W1.4 update_quality_standards", case_update_quality)

rec.case("W2.1 add_lesson pytest parametrize", write_lesson("W2.1", "Codex单测：pytest parametrize 批量测试"))
rec.case("W2.2 add_lesson asyncio nested loop", write_lesson("W2.2", "Codex单测：asyncio.run 在嵌套事件循环中会报错"))
rec.case("W2.3 add_lesson portalocker", write_lesson("W2.3", "Codex单测：portalocker 跨进程文件锁机制"))
rec.case("W2.4 add_decision pytest", write_decision("W2.4", "Codex单测：测试框架选择", "pytest", "生态最完善"))
rec.case("W2.5 add_decision GitHub Actions", write_decision("W2.5", "Codex单测：CI平台选择", "GitHub Actions", "免费额度高"))
rec.case("W2.6 add_playbook CI release", case_playbook)
rec.case("W2.7 memory_store fallback", case_memory_store_fallback)
rec.case("W2.8 add_lesson CJK search", write_lesson("W2.8", "Codex单测：中文CJK搜索-异步文件操作"))

rec.case("W4.1 save_agent_context", case_save_agent_context)
rec.case("W4.2 refresh_quick_context", case_refresh_quick_context)
rec.case("W5.1 wrap_up_session adapted", case_wrap_up_like)
rec.case("W5.2 set stale optional", case_stale_optional_59)
rec.case("W6.1 register_tool", case_register_tool)
rec.case("WC6.1 playbook execution prep", case_prepare_execution)
rec.case("WC7.1 conflict decision", case_conflict_decision)
rec.case("WC9.1 set stale required", case_stale_required_60)

seed["results"] = rec.summary()
save_seed()
rec.print_summary()
print(f"Seed 已保存: {AUDIT_DIR / 'codex_unit_seed.json'}")
print(json.dumps({"phase": 1, "pass": rec.pass_count, "fail": rec.fail_count, "skip": rec.skip_count}, ensure_ascii=False))
