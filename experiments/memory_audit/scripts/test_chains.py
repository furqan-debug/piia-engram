from __future__ import annotations

import json
import tempfile
from pathlib import Path

from _audit_common import (
    RESULTS_DIR,
    CaseRecorder,
    Engram,
    ensure_decision,
    ensure_lesson,
    ensure_playbook,
    flatten_search,
    set_lesson_last_reviewed,
    status_table,
    wrap_up_like_session,
)


def make_engram() -> tuple[Engram, str]:
    tmp = tempfile.mkdtemp(prefix="engram_chain_")
    return Engram(root=Path(tmp)), tmp


rec = CaseRecorder("Phase 2 集成链", expected_total=10)


def chain_c1_identity_context():
    eng, tmp = make_engram()
    eng.update_profile({"role": "chain_codex_tester", "language": "zh"})
    ctx = eng.generate_context(level="quick")
    ok = "chain_codex_tester" in ctx
    return ok, f"tmp={tmp}; role_in_context={ok}", {"tmp": tmp}


def chain_c2_write_search_count():
    eng, tmp = make_engram()
    lesson = ensure_lesson(eng, "chain C2 pytest parametrize access count check", domain="chain_test")
    first = eng.search_knowledge("pytest parametrize", scope="lessons", limit=5)
    before = flatten_search(first)[0].get("access_count", 0) if flatten_search(first) else 0
    eng.get_lessons(domain="chain_test")
    second = eng.search_knowledge("pytest parametrize", scope="lessons", limit=5)
    after = flatten_search(second)[0].get("access_count", 0) if flatten_search(second) else 0
    ok = bool(lesson.get("id")) and after > before
    return ok, f"tmp={tmp}; access_count {before}->{after}", {"tmp": tmp, "lesson_id": lesson.get("id")}


def chain_c3_staging_promotion():
    eng, tmp = make_engram()
    lesson = ensure_lesson(eng, "chain C3 staging promotion target", domain="chain_test", tier="staging")
    path = eng._knowledge_dir / "lessons.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for item in data:
        if item.get("id") == lesson.get("id"):
            item["access_count"] = 3
            item["tier"] = "staging"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    result = eng.evaluate_tiers()
    refreshed = [l for l in eng.get_lessons(domain="chain_test", _update_access=False) if l.get("id") == lesson.get("id")]
    tier = refreshed[0].get("tier") if refreshed else ""
    ok = tier == "verified" and result.get("promoted", 0) >= 1
    return ok, f"tmp={tmp}; tier={tier}; promoted={result.get('promoted')}", {"tmp": tmp}


def chain_c4_session_recovery():
    eng, tmp = make_engram()
    marker = "chain C4 recoverable context marker"
    saved = eng.save_agent_context(tool="codex", content=marker, project_folder=tmp)
    recent = eng.get_recent_context(tool="codex", limit=1)
    ok = bool(saved.get("session_id")) and recent and marker in recent[0].get("content", "")
    return ok, f"tmp={tmp}; session_id={saved.get('session_id')}", {"tmp": tmp}


def chain_c5_wrap_up_full():
    eng, tmp = make_engram()
    summary = "chain C5：注意部署前必须检查环境变量。我们决定使用 pytest 作为测试入口。"
    result = wrap_up_like_session(eng, summary=summary, project_folder=tmp)
    lessons = eng.get_lessons(limit=None, _update_access=False)
    decisions = eng.get_decisions(limit=None, _update_access=False)
    ok = (result["insights"].get("saved_lessons", 0) + result["insights"].get("saved_decisions", 0)) >= 1
    ok = ok and (len(lessons) + len(decisions) >= 1)
    return ok, f"tmp={tmp}; insights={result['insights']}", {"tmp": tmp}


def chain_c6_playbook_execution():
    eng, tmp = make_engram()
    pb = ensure_playbook(
        eng,
        "chain C6 deploy flow",
        steps=[
            {"order": 1, "action": "build"},
            {"order": 2, "action": "test"},
            {"order": 3, "action": "deploy"},
        ],
        domain="chain_test",
        triggers=["chain_deploy"],
    )
    eng.prepare_playbook_execution(pb["id"])
    eng.update_execution_step(pb["id"], 1, "completed")
    eng.update_execution_step(pb["id"], 2, "completed")
    status = eng.get_execution_status(pb["id"])
    ok = status.get("completed") == 2 and status.get("total") == 3
    return ok, f"tmp={tmp}; completed={status.get('completed')}/{status.get('total')}", {"tmp": tmp}


def chain_c7_conflict_detection():
    eng, tmp = make_engram()
    ensure_decision(eng, "CI platform choice", "GitHub Actions", domain="chain_conflict")
    ensure_decision(eng, "CI runner final policy", "GitLab CI", domain="chain_conflict")
    decisions = eng.get_decisions(limit=None, _update_access=False)
    conflicts = eng._detect_decision_conflicts(decisions)
    ctx = eng.generate_context(level="full")
    ok = bool(conflicts) and ("conflict" in ctx.lower() or "冲突" in ctx or conflicts)
    return ok, f"tmp={tmp}; conflicts={len(conflicts)}", {"tmp": tmp, "conflicts": conflicts}


def chain_c8_dedup_merge():
    eng, tmp = make_engram()
    ensure_lesson(eng, "database migration requires backup before deploy", domain="chain_merge")
    ensure_lesson(eng, "database schema change should create backup before release", domain="chain_merge")
    merges = eng.suggest_merges(threshold=0.2, limit=10)
    suggestions = merges.get("suggestions") or merges.get("merges") or []
    ok = bool(suggestions) or merges.get("total", 0) > 0
    return ok, f"tmp={tmp}; suggestions={len(suggestions)} total={merges.get('total')}", {"tmp": tmp, "merges": merges}


def chain_c9_health_linkage():
    eng, tmp = make_engram()
    fresh = ensure_lesson(eng, "chain C9 fresh health lesson", domain="chain_health")
    before = eng.get_health_report().get("health_score", 0)
    stale = ensure_lesson(eng, "chain C9 stale health lesson", domain="chain_health")
    set_lesson_last_reviewed(eng, stale["id"], days_ago=61)
    after_report = eng.get_health_report()
    stale_result = eng.get_stale_knowledge(days=30, limit=None)
    stale_hit = any(item.get("id") == stale["id"] for item in stale_result.get("lessons", []))
    ok = fresh.get("id") and stale_hit and 0 <= after_report.get("health_score", 0) <= 100
    return ok, f"tmp={tmp}; health {before}->{after_report.get('health_score')}; stale_hit={stale_hit}", {"tmp": tmp}


def chain_c10_identity_card():
    eng, tmp = make_engram()
    eng.update_profile({"role": "chain_identity_card_user", "language": "zh"})
    eng.update_preferences({"communication": "direct"})
    eng.update_work_style({"preferences": {"mode": "audit"}, "communication": "direct"})
    eng.update_quality_standards({"acceptance_threshold": 4, "rules": ["chain quality rule"]})
    ensure_lesson(eng, "chain C10 identity card lesson", domain="chain_identity")
    ensure_decision(eng, "chain identity card decision", "record it", domain="chain_identity")
    card = eng.export_identity_card()
    ok = "chain_identity_card_user" in card and "chain quality rule" in card and "chain C10" in card
    return ok, f"tmp={tmp}; card_len={len(card)}", {"tmp": tmp}


print("========== Phase 2: test_chains.py ==========")
rec.case("C1 身份→上下文", chain_c1_identity_context)
rec.case("C2 写入→搜索→计数", chain_c2_write_search_count)
rec.case("C3 Staging→晋升", chain_c3_staging_promotion)
rec.case("C4 Session保存→恢复", chain_c4_session_recovery)
rec.case("C5 wrap_up全链", chain_c5_wrap_up_full)
rec.case("C6 Playbook执行链", chain_c6_playbook_execution)
rec.case("C7 冲突检测", chain_c7_conflict_detection)
rec.case("C8 Dedup→合并", chain_c8_dedup_merge)
rec.case("C9 Health联动", chain_c9_health_linkage)
rec.case("C10 Identity Card聚合", chain_c10_identity_card)

report = (
    "# Engram 集成链审计报告\n\n"
    f"日期: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    f"结果: {rec.pass_count}/10 PASS, {rec.fail_count} FAIL, {rec.skip_count} SKIP\n\n"
    + status_table(rec.results)
    + "\n\n## 说明\n\n每条链均使用独立临时 Engram(root=tmp) 实例，不影响真实数据。\n"
)
(RESULTS_DIR / "chains_report.md").write_text(report, encoding="utf-8")
(RESULTS_DIR / "chains_results.json").write_text(json.dumps(rec.summary(), ensure_ascii=False, indent=2), encoding="utf-8")
rec.print_summary()
print(f"Report 已保存: {RESULTS_DIR / 'chains_report.md'}")
print(json.dumps({"phase": 2, "pass": rec.pass_count, "fail": rec.fail_count, "skip": rec.skip_count}, ensure_ascii=False))
