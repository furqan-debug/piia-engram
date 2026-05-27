from __future__ import annotations

import json
from pathlib import Path

from _audit_common import (
    AUDIT_DIR,
    REPO,
    RESULTS_DIR,
    CaseRecorder,
    Engram,
    contains_text,
    dump_json,
    ensure_decision,
    ensure_lesson,
    ensure_playbook,
    flatten_search,
    now_iso,
    status_table,
)


PROJECT = str(REPO).replace("\\", "/")
CODEX_DOMAIN = "cross_ai_test_codex"
CODEX_SOURCE = "codex"
CLAUDE_SOURCE = "claude_code"


eng = Engram()
rec = CaseRecorder("Phase 4 跨 AI 验证", expected_total=23)
seed: dict = {
    "written_at": now_iso(),
    "phase": "cross_ai_codex",
    "source_tool": CODEX_SOURCE,
    "items": {},
}


def detect_claude_dataset() -> dict:
    cross_lessons = eng.get_lessons(domain="cross_ai_test", limit=None, _update_access=False)
    if cross_lessons:
        return {
            "domain": "cross_ai_test",
            "query": "跨AI测试",
            "tool": "cross_ai_test_tool",
            "playbook_marker": "跨AI测试",
            "context_markers": ["cross_ai", "Cross-AI", "cross_ai_test"],
            "blocked": False,
            "note": "detected cross_ai_test domain",
        }
    cc_seed = AUDIT_DIR / "cc_self_test_seed.json"
    cc_lessons = eng.get_lessons(domain="cc_self_test", limit=None, _update_access=False)
    if cc_seed.is_file() and cc_lessons:
        return {
            "domain": "cc_self_test",
            "query": "CC自测",
            "tool": "cc_self_test_tool",
            "playbook_marker": "CC自测",
            "context_markers": ["cc_self_test", "CC自测", "cross_ai", "Cross-AI"],
            "blocked": False,
            "note": "cross_ai_test domain absent; using cc_self_test dataset because cc_self_test_seed.json exists",
        }
    return {
        "domain": "cross_ai_test",
        "query": "跨AI测试",
        "tool": "cross_ai_test_tool",
        "playbook_marker": "跨AI测试",
        "context_markers": ["cross_ai", "Cross-AI"],
        "blocked": True,
        "note": "BLOCKED: Phase 1 data not found",
    }


dataset = detect_claude_dataset()
READ_DOMAIN = dataset["domain"]


def read_results(query: str, scope: str = "all", filters: dict | None = None, limit: int = 20) -> list[dict]:
    return flatten_search(eng.search_knowledge(query, scope=scope, filters=filters, limit=limit))


def blocked_detail() -> tuple[bool, str, dict]:
    return False, dataset["note"], {"blocked": True, "dataset": dataset}


def r1_search_cross_ai():
    if dataset["blocked"]:
        return blocked_detail()
    hits = read_results(dataset["query"], limit=30)
    if len(hits) < 3 and READ_DOMAIN == "cc_self_test":
        hits = read_results("cc_self_test", limit=30)
    ok = len(hits) >= 3
    return ok, f"dataset={READ_DOMAIN}; query={dataset['query']}; hits={len(hits)}", {"dataset": dataset}


def r2_pytest_domain():
    if dataset["blocked"]:
        return blocked_detail()
    hits = read_results("pytest", filters={"domain": READ_DOMAIN}, limit=20)
    ok = bool(hits)
    return ok, f"domain={READ_DOMAIN}; hits={len(hits)}", None


def r3_lessons_domain():
    if dataset["blocked"]:
        return blocked_detail()
    lessons = eng.get_lessons(domain=READ_DOMAIN, limit=None, _update_access=False)
    ok = len(lessons) >= 2 and any(l.get("source_tool") == CLAUDE_SOURCE for l in lessons)
    return ok, f"domain={READ_DOMAIN}; lessons={len(lessons)}", None


def r4_decision_deploy():
    if dataset["blocked"]:
        return blocked_detail()
    decisions = eng.get_decisions(limit=None, source_tool=CLAUDE_SOURCE, _update_access=False)
    ok = any("部署" in (d.get("question") or d.get("title") or "") for d in decisions)
    return ok, f"claude_decisions={len(decisions)}", None


def r5_file_lock_search():
    if dataset["blocked"]:
        return blocked_detail()
    hits = read_results("文件锁", scope="lessons", limit=20)
    ok = any(contains_text(item, "文件锁") or contains_text(item, "portalocker") for item in hits)
    return ok, f"hits={len(hits)}", None


def r6_playbook_exists():
    if dataset["blocked"]:
        return blocked_detail()
    pbs = eng.get_playbooks(domain=READ_DOMAIN, limit=None, _update_access=False)
    ok = any(dataset["playbook_marker"] in pb.get("title", "") or pb.get("source_tool") == CLAUDE_SOURCE for pb in pbs)
    pb_id = pbs[0].get("id") if pbs else ""
    seed["phase2_playbook_id"] = pb_id
    return ok, f"domain={READ_DOMAIN}; playbooks={len(pbs)}; id={pb_id}", {"playbook_id": pb_id}


def r7_playbook_steps():
    if dataset["blocked"]:
        return blocked_detail()
    pb_id = seed.get("phase2_playbook_id", "")
    if not pb_id:
        pbs = eng.get_playbooks(domain=READ_DOMAIN, limit=None, _update_access=False)
        pb_id = pbs[0].get("id") if pbs else ""
    pb = eng.get_playbook(pb_id, _update_access=False) if pb_id else {"error": "missing playbook id"}
    ok = not pb.get("error") and len(pb.get("steps", [])) >= 3
    return ok, f"id={pb_id}; steps={len(pb.get('steps', []))}", None


def r8_profile_marker():
    profile = eng.get_profile()
    desc = profile.get("description", "")
    ok = "cross_ai_test_marker" in desc or "cc_self_test_marker" in desc
    return ok, f"description={desc}", None


def r9_recent_claude_context():
    sessions = eng.get_recent_context(tool=CLAUDE_SOURCE, limit=10)
    text = "\n".join(s.get("content", "") for s in sessions)
    ok = any(marker in text for marker in dataset["context_markers"])
    return ok, f"sessions={len(sessions)}; dataset={READ_DOMAIN}", None


def r10_find_tool():
    if dataset["blocked"]:
        return blocked_detail()
    hits = eng.find_tool(dataset["tool"])
    ok = any(t.get("name") == dataset["tool"] for t in hits)
    return ok, f"tool={dataset['tool']}; hits={len(hits)}", None


def r11_relevant_knowledge():
    lessons = eng.get_relevant_lessons(PROJECT, limit=8, _update_access=False)
    if not lessons:
        lessons = eng.get_knowledge_inheritance("Engram cross AI memory audit", limit=8).get("items", [])
    return bool(lessons), f"items={len(lessons)}", None


def r12_memory_store_route():
    hits = read_results("memory_store 统一路由", scope="lessons", limit=20)
    ok = any("memory_store" in (item.get("summary", "") + item.get("detail", "")) for item in hits)
    return ok, f"hits={len(hits)}", None


def r13_project_context():
    snapshot = eng.get_project_snapshot(PROJECT)
    return bool(snapshot), f"keys={sorted(snapshot.keys()) if snapshot else []}", None


def r14_user_context_standard():
    ctx = eng.generate_context(PROJECT, level="standard")
    ok = any(marker in ctx for marker in dataset["context_markers"])
    return ok, f"len={len(ctx)}; dataset={READ_DOMAIN}", None


def r15_list_claude_sessions():
    sessions = eng.list_agent_sessions(tool=CLAUDE_SOURCE, limit=20)
    return len(sessions) >= 1, f"sessions={len(sessions)}", None


def remember(key: str, value: dict) -> dict:
    seed["items"][key] = value
    return value


def cw1_lesson_cicd():
    summary = "跨AI测试：Codex写入的CI/CD经验"
    lesson = ensure_lesson(eng, summary, domain=CODEX_DOMAIN, source_tool=CODEX_SOURCE)
    ok = bool(lesson.get("id"))
    return ok, f"id={lesson.get('id')}", remember("CW1", {"id": lesson.get("id"), "summary": summary})


def cw2_decision_cache():
    decision = ensure_decision(
        eng,
        "跨AI测试Codex：缓存策略",
        "Redis",
        reasoning="内存快",
        domain=CODEX_DOMAIN,
        source_tool=CODEX_SOURCE,
    )
    ok = bool(decision.get("id")) and decision.get("choice") == "Redis"
    return ok, f"id={decision.get('id')}", remember("CW2", {"id": decision.get("id"), "choice": "Redis"})


def cw3_playbook_deploy():
    pb = ensure_playbook(
        eng,
        "codex_cross_ai_deploy_flow_20260527",
        steps=[{"order": 1, "action": "build"}, {"order": 2, "action": "deploy"}],
        domain=CODEX_DOMAIN,
        source_tool=CODEX_SOURCE,
        triggers=["codex_cross_ai_deploy"],
    )
    ok = bool(pb.get("id")) and len(pb.get("steps", [])) == 2
    return ok, f"id={pb.get('id')} steps={len(pb.get('steps', []))}", remember(
        "CW3",
        {"id": pb.get("id"), "title": pb.get("title"), "steps_count": len(pb.get("steps", []))},
    )


def cw4_save_context():
    content = f"Cross-AI test by Codex at {now_iso()}"
    result = eng.save_agent_context(tool=CODEX_SOURCE, content=content, project_folder=PROJECT)
    ok = bool(result.get("session_id"))
    return ok, f"session_id={result.get('session_id')}", remember("CW4", result)


def cw5_register_tool():
    result = eng.register_tool(
        {
            "name": "codex_cross_ai_tool",
            "path": "/codex/cross",
            "category": "runtime",
            "version": "1.0",
            "purpose": "Codex cross-AI audit tool",
        },
        registered_by=CODEX_SOURCE,
    )
    ok = result.get("name") == "codex_cross_ai_tool"
    return ok, f"action={result.get('_action')} id={result.get('id')}", remember("CW5", result)


def cw6_lesson_typescript():
    summary = "跨AI测试Codex：TypeScript类型安全实践"
    lesson = ensure_lesson(eng, summary, domain=CODEX_DOMAIN, source_tool=CODEX_SOURCE)
    ok = bool(lesson.get("id"))
    return ok, f"id={lesson.get('id')}", remember("CW6", {"id": lesson.get("id"), "summary": summary})


def cw7_decision_logging():
    decision = ensure_decision(
        eng,
        "跨AI测试Codex：日志方案",
        "structured logging",
        reasoning="可观测",
        domain=CODEX_DOMAIN,
        source_tool=CODEX_SOURCE,
    )
    ok = bool(decision.get("id")) and decision.get("choice") == "structured logging"
    return ok, f"id={decision.get('id')}", remember("CW7", {"id": decision.get("id"), "choice": decision.get("choice")})


def cw8_project_snapshot():
    folder = f"{PROJECT}/cross_ai_test_codex"
    data = {
        "title": "Codex cross-AI test snapshot",
        "summary": "Codex cross-AI test snapshot",
        "tech_stack": ["python", "mcp", "engram"],
        "known_issues": [],
        "notes": "cross_ai_test_codex",
    }
    eng.save_project_snapshot(folder, data)
    snapshot = eng.get_project_snapshot(folder)
    ok = snapshot.get("summary") == "Codex cross-AI test snapshot" or snapshot.get("title") == data["title"]
    return ok, f"folder={folder}", remember("CW8", {"project_folder": folder, "snapshot": snapshot})


print("========== Phase 4: test_cross_ai_codex.py ==========")
print(f"Phase 2 dataset: {READ_DOMAIN} ({dataset['note']})")

for name, func in [
    ("R1 search cross/cc AI marker", r1_search_cross_ai),
    ("R2 pytest domain filter", r2_pytest_domain),
    ("R3 lessons domain source", r3_lessons_domain),
    ("R4 deployment decision", r4_decision_deploy),
    ("R5 CJK file lock search", r5_file_lock_search),
    ("R6 playbook exists", r6_playbook_exists),
    ("R7 playbook steps", r7_playbook_steps),
    ("R8 profile marker", r8_profile_marker),
    ("R9 recent Claude context", r9_recent_claude_context),
    ("R10 find Claude tool", r10_find_tool),
    ("R11 relevant knowledge", r11_relevant_knowledge),
    ("R12 memory_store route", r12_memory_store_route),
    ("R13 project context", r13_project_context),
    ("R14 standard context", r14_user_context_standard),
    ("R15 list Claude sessions", r15_list_claude_sessions),
    ("CW1 Codex lesson CI/CD", cw1_lesson_cicd),
    ("CW2 Codex decision cache", cw2_decision_cache),
    ("CW3 Codex playbook deploy", cw3_playbook_deploy),
    ("CW4 Codex context", cw4_save_context),
    ("CW5 Codex tool", cw5_register_tool),
    ("CW6 Codex lesson TypeScript", cw6_lesson_typescript),
    ("CW7 Codex decision logging", cw7_decision_logging),
    ("CW8 Codex project snapshot", cw8_project_snapshot),
]:
    rec.case(name, func)

seed["phase2_dataset"] = dataset
seed["results"] = rec.summary()
dump_json(AUDIT_DIR / "cross_ai_codex_seed.json", seed)

read_results_cases = [r for r in rec.results if r["name"].startswith("R")]
write_results_cases = [r for r in rec.results if r["name"].startswith("CW")]
read_pass = sum(1 for r in read_results_cases if r["status"] == "PASS")
write_pass = sum(1 for r in write_results_cases if r["status"] == "PASS")
overall = "PASS" if read_pass == 15 and write_pass == 8 else "PARTIAL" if write_pass == 8 else "FAIL"

report = [
    "# Cross-AI Memory Audit — Codex Side",
    "",
    f"日期: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}",
    f"Claude 数据集: {READ_DOMAIN}",
    f"说明: {dataset['note']}",
    "",
    f"## Phase 2: 盲读验证 ({read_pass}/15)",
    "",
    status_table(read_results_cases),
    "",
    f"## Phase 3: Codex 写入 ({write_pass}/8)",
    "",
    status_table(write_results_cases),
    "",
    "## 跨 AI 互通性评估",
    "",
    f"- Claude Code 写入 -> Codex 可见: {read_pass}/15",
    f"- Codex 写入成功: {write_pass}/8",
    f"- 总体评估: {overall}",
]
(RESULTS_DIR / "cross_ai_codex_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
(RESULTS_DIR / "cross_ai_codex_results.json").write_text(json.dumps(rec.summary(), ensure_ascii=False, indent=2), encoding="utf-8")

rec.print_summary()
print(f"Seed 已保存: {AUDIT_DIR / 'cross_ai_codex_seed.json'}")
print(f"Report 已保存: {RESULTS_DIR / 'cross_ai_codex_report.md'}")
print(json.dumps({"phase": 4, "read_pass": read_pass, "write_pass": write_pass, "pass": rec.pass_count, "fail": rec.fail_count}, ensure_ascii=False))

