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
    flatten_search,
    load_json,
    set_lesson_last_reviewed,
    status_table,
)


DOMAIN = "codex_unit_test"
SOURCE = "codex"
PROJECT = str(REPO).replace("\\", "/")
SEED_PATH = AUDIT_DIR / "codex_unit_seed.json"


eng = Engram()
seed = load_json(SEED_PATH, {})
items = seed.get("items", {})
rec = CaseRecorder("Phase 3 单元验证", expected_total=46)


def seed_id(key: str) -> str:
    return str(items.get(key, {}).get("id", ""))


def all_search(query: str, scope: str = "all", limit: int = 20, filters: dict | None = None) -> list[dict]:
    return flatten_search(eng.search_knowledge(query, scope=scope, limit=limit, filters=filters))


def has_hit(query: str, needle: str = "", scope: str = "all", filters: dict | None = None) -> bool:
    results = all_search(query, scope=scope, filters=filters)
    if not needle:
        return bool(results)
    return any(contains_text(item, needle) for item in results)


def report_group(name: str, case_prefixes: list[str]) -> tuple[int, int]:
    selected = [r for r in rec.results if any(r["name"].startswith(prefix) for prefix in case_prefixes)]
    return sum(1 for r in selected if r["status"] == "PASS"), len(selected)


def v11_profile_role():
    profile = eng.get_profile()
    return profile.get("role") == "codex_tester", f"role={profile.get('role')}", None


def v12_profile_description():
    desc = eng.get_profile().get("description", "")
    return "codex_unit_test_marker" in desc, f"description={desc}", None


def v13_preferences():
    prefs = eng.get_preferences()
    return prefs.get("communication") == "sync", f"communication={prefs.get('communication')}", None


def v14_trust():
    restricted = set(eng.get_trust_boundaries().get("restricted_fields", []))
    return "email" in restricted, f"restricted={sorted(restricted)}", None


def v15_quality():
    rules = eng.get_quality_standards().get("rules", [])
    return "codex_unit_test_rule" in rules, f"rules={rules}", None


def v16_safe_profile():
    safe = eng.get_profile(safe=True)
    ok = "email" not in safe and "phone" not in safe
    return ok, f"safe_keys={sorted(safe.keys())}", None


def v21_lessons_count():
    lessons = eng.get_lessons(domain=DOMAIN, limit=None, _update_access=False)
    return len(lessons) >= 4, f"count={len(lessons)}", None


def v22_search_pytest():
    hits = all_search("pytest parametrize", scope="lessons")
    ok = any(item.get("source_tool") == SOURCE and contains_text(item, "pytest parametrize") for item in hits)
    return ok, f"hits={len(hits)}", None


def v23_search_asyncio():
    hits = all_search("asyncio 嵌套 事件循环", scope="lessons")
    ok = any(contains_text(item, "asyncio.run") or contains_text(item, "嵌套事件循环") for item in hits)
    return ok, f"hits={len(hits)}", None


def v24_search_file_lock():
    hits = all_search("文件锁", scope="lessons")
    ok = any(contains_text(item, "文件锁") or contains_text(item, "portalocker") for item in hits)
    return ok, f"hits={len(hits)}", None


def v25_decision_pytest():
    decisions = eng.get_decisions(limit=None, _update_access=False)
    ok = any(("测试框架" in (d.get("question") or d.get("title") or "")) and d.get("choice") == "pytest" for d in decisions)
    return ok, f"decisions={len(decisions)}", None


def v26_decision_github_actions():
    decisions = eng.get_decisions(limit=None, _update_access=False)
    ok = any(("CI平台" in (d.get("question") or d.get("title") or "")) and d.get("choice") == "GitHub Actions" for d in decisions)
    return ok, f"decisions={len(decisions)}", None


def v27_playbook_exists():
    pbs = eng.get_playbooks(domain=DOMAIN, limit=None, _update_access=False)
    expected = items.get("W2.6", {}).get("expected_title") or items.get("W2.6", {}).get("title", "")
    ok = any(pb.get("id") == seed_id("W2.6") or pb.get("title") == expected for pb in pbs)
    return ok, f"playbooks={len(pbs)}", None


def v28_playbook_steps():
    pb_id = seed_id("W2.6")
    pb = eng.get_playbook(pb_id, _update_access=False)
    ok = not pb.get("error") and len(pb.get("steps", [])) == 3
    return ok, f"id={pb_id}; steps={len(pb.get('steps', []))}", None


def v29_memory_store_search():
    return has_hit("memory_store 路由", "memory_store", scope="lessons"), "query=memory_store 路由", None


def v210_lesson_sources():
    lessons = eng.get_lessons(domain=DOMAIN, limit=None, _update_access=False)
    bad = [l.get("id") for l in lessons if l.get("source_tool") != SOURCE]
    return not bad and bool(lessons), f"lessons={len(lessons)} bad={bad}", None


def v31_search_all_count():
    hits = all_search("Codex单测", scope="all", limit=30)
    return len(hits) >= 5, f"hits={len(hits)}", None


def v32_scope_lessons():
    result = eng.search_knowledge("Codex单测", scope="lessons", limit=30)
    ok = bool(result.get("lessons")) and not result.get("decisions") and not result.get("playbooks")
    return ok, f"lessons={len(result.get('lessons', []))}", None


def v33_filter_domain():
    result = eng.search_knowledge("Codex单测", scope="all", limit=30, filters={"domain": DOMAIN})
    hits = flatten_search(result)
    ok = bool(hits) and all(DOMAIN in (item.get("domain") or "") for item in hits)
    return ok, f"hits={len(hits)}", None


def v34_find_similar():
    result = eng.find_similar_knowledge(seed_id("W2.1"), limit=5)
    ok = result.get("total", 0) >= 1
    return ok, f"total={result.get('total')}", None


def v35_suggest_merges():
    result = eng.suggest_merges(threshold=0.2, limit=30)
    suggestions = result.get("suggestions", [])
    ok = len(suggestions) >= 1
    return ok, f"suggestions={len(suggestions)}", None


def v36_relevant_knowledge():
    lessons = eng.get_relevant_lessons(PROJECT, limit=8, _update_access=False)
    if not lessons:
        inherited = eng.get_knowledge_inheritance("Engram memory audit python mcp", limit=8)
        lessons = inherited.get("items", [])
    return bool(lessons), f"items={len(lessons)}", None


def v41_recent_context():
    sessions = eng.get_recent_context(tool=SOURCE, limit=10)
    ok = any("Codex单测跨执行验证" in s.get("content", "") for s in sessions)
    return ok, f"sessions={len(sessions)}", None


def v42_list_sessions():
    sessions = eng.list_agent_sessions(tool=SOURCE, limit=20)
    return len(sessions) >= 1, f"sessions={len(sessions)}", None


def v43_context_quick():
    ctx = eng.generate_context(PROJECT, level="quick")
    return "codex_tester" in ctx, f"len={len(ctx)}", None


def v44_context_standard():
    ctx = eng.generate_context(PROJECT, level="standard")
    ok = "codex_unit_test" in ctx or "codex_unit_test_marker" in ctx or "Codex单测" in ctx
    return ok, f"len={len(ctx)}", None


def v45_context_full_longer():
    standard = eng.generate_context(PROJECT, level="standard")
    full = eng.generate_context(PROJECT, level="full")
    return len(full) > len(standard), f"standard={len(standard)} full={len(full)}", None


def v46_quick_context_file():
    path = eng.root / "quick_context.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    ok = path.is_file() and ("codex_tester" in text or "关于用户" in text or "Who I Am" in text)
    return ok, f"path={path}; len={len(text)}", None


def v51_wrapup_knowledge():
    lessons = eng.get_lessons(limit=None, _update_access=False)
    decisions = eng.get_decisions(limit=None, _update_access=False)
    ok = any("异步修复" in l.get("summary", "") for l in lessons) or any(
        "asyncio" in (d.get("title") or d.get("question") or "") for d in decisions
    )
    return ok, f"lessons={len(lessons)} decisions={len(decisions)}", None


def v52_overview():
    overview = eng.get_knowledge_overview()
    health = overview.get("health", {})
    summary = health.get("summary", {})
    ok = "total_lessons" in summary and "health_score" in health
    return ok, f"health_score={health.get('health_score')} total_lessons={summary.get('total_lessons')}", None


def v53_project_context():
    snapshot = eng.get_project_snapshot(PROJECT)
    ok = bool(snapshot) and (snapshot.get("title") or snapshot.get("notes") or snapshot.get("known_issues"))
    return ok, f"keys={sorted(snapshot.keys()) if snapshot else []}", None


def v54_identity_card():
    card = eng.export_identity_card()
    set_lesson_last_reviewed(eng, seed_id("W2.1"), days_ago=60)
    return "codex_tester" in card, f"len={len(card)}", None


def v55_stale_knowledge():
    lesson_id = seed_id("W2.1")
    stale = eng.get_stale_knowledge(days=30, limit=None)
    ok = any(item.get("id") == lesson_id for item in stale.get("lessons", []))
    return ok, f"stale_lessons={len(stale.get('lessons', []))}", None


def v56_health_score_range():
    health = eng.get_knowledge_overview().get("health", {})
    score = health.get("health_score")
    return isinstance(score, int | float) and 0 <= score <= 100, f"health_score={score}", None


def v61_find_tool():
    result = eng.find_tool("codex_unit_test_tool")
    ok = any(t.get("name") == "codex_unit_test_tool" for t in result)
    return ok, f"hits={len(result)}", None


def v62_list_tools():
    tools = eng.list_tools()
    ok = any(t.get("name") == "codex_unit_test_tool" for t in tools)
    return ok, f"tools={len(tools)}", None


def v63_tool_version():
    result = eng.find_tool("codex_unit_test_tool")
    version = next((t.get("version") for t in result if t.get("name") == "codex_unit_test_tool"), "")
    return version == "2.0", f"version={version}", None


def vc11():
    return v43_context_quick()


def vc21():
    hits = all_search("pytest parametrize", scope="lessons")
    access = max([int(item.get("access_count", 0)) for item in hits] or [0])
    return access > 0, f"max_access_count={access}", None


def vc51():
    return v51_wrapup_knowledge()


def vc61():
    status = eng.get_execution_status(seed_id("W2.6"))
    ok = status.get("completed") == 2 and status.get("total") == 3
    return ok, f"completed={status.get('completed')}/{status.get('total')}", None


def vc71():
    decisions = eng.get_decisions(limit=None, _update_access=False)
    text = "\n".join(d.get("choice", "") for d in decisions)
    return "GitHub Actions" in text and "GitLab CI" in text, f"choices_present={('GitHub Actions' in text, 'GitLab CI' in text)}", None


def vc81():
    return v35_suggest_merges()


def vc91():
    return v55_stale_knowledge()


def vc101():
    card = eng.export_identity_card()
    set_lesson_last_reviewed(eng, seed_id("W2.1"), days_ago=60)
    checks = ["codex_tester" in card, "codex_unit_test_rule" in card, "Codex单测" in card, "pytest" in card]
    return all(checks), f"checks={checks}; len={len(card)}", None


def vc_persist():
    required = [SEED_PATH, RESULTS_DIR / "unit_write_log.txt", RESULTS_DIR / "chains_report.md"]
    ok = all(path.is_file() for path in required) and rec.fail_count == 0
    return ok, f"required_files={[str(p) for p in required]}", None


print("========== Phase 3: unit_verify.py ==========")
if not SEED_PATH.is_file():
    raise SystemExit(f"missing seed: {SEED_PATH}")

cases = [
    ("V1.1 profile role", v11_profile_role),
    ("V1.2 profile description", v12_profile_description),
    ("V1.3 preferences communication", v13_preferences),
    ("V1.4 trust restricted_fields", v14_trust),
    ("V1.5 quality rules", v15_quality),
    ("V1.6 safe profile", v16_safe_profile),
    ("V2.1 lessons count", v21_lessons_count),
    ("V2.2 search pytest", v22_search_pytest),
    ("V2.3 search asyncio", v23_search_asyncio),
    ("V2.4 search file lock", v24_search_file_lock),
    ("V2.5 decision pytest", v25_decision_pytest),
    ("V2.6 decision GitHub Actions", v26_decision_github_actions),
    ("V2.7 playbook exists", v27_playbook_exists),
    ("V2.8 playbook steps", v28_playbook_steps),
    ("V2.9 memory_store route", v29_memory_store_search),
    ("V2.10 lesson source_tool", v210_lesson_sources),
    ("V3.1 search all count", v31_search_all_count),
    ("V3.2 scope lessons", v32_scope_lessons),
    ("V3.3 filter domain", v33_filter_domain),
    ("V3.4 find similar", v34_find_similar),
    ("V3.5 suggest merges", v35_suggest_merges),
    ("V3.6 relevant knowledge", v36_relevant_knowledge),
    ("V4.1 recent context", v41_recent_context),
    ("V4.2 list sessions", v42_list_sessions),
    ("V4.3 context quick", v43_context_quick),
    ("V4.4 context standard", v44_context_standard),
    ("V4.5 context full longer", v45_context_full_longer),
    ("V4.6 quick_context file", v46_quick_context_file),
    ("V5.1 wrapup knowledge", v51_wrapup_knowledge),
    ("V5.2 overview", v52_overview),
    ("V5.3 project context", v53_project_context),
    ("V5.4 identity card", v54_identity_card),
    ("V5.5 stale knowledge", v55_stale_knowledge),
    ("V5.6 health score range", v56_health_score_range),
    ("V6.1 find tool", v61_find_tool),
    ("V6.2 list tools", v62_list_tools),
    ("V6.3 tool version", v63_tool_version),
    ("VC1.1 context quick", vc11),
    ("VC2.1 search access_count", vc21),
    ("VC5.1 wrapup searchable", vc51),
    ("VC6.1 execution status", vc61),
    ("VC7.1 conflicting choices", vc71),
    ("VC8.1 merge suggestions", vc81),
    ("VC9.1 stale lesson", vc91),
    ("VC10.1 identity card aggregate", vc101),
    ("VC-persist cross process", vc_persist),
]

for name, func in cases:
    rec.case(name, func)

version = "unknown"
pyproject = REPO / "pyproject.toml"
if pyproject.is_file():
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.startswith("version ="):
            version = line.split("=", 1)[1].strip().strip('"')
            break

groups = [
    ("S1 身份层", ["V1."]),
    ("S2 知识层", ["V2."]),
    ("S3 检索层", ["V3."]),
    ("S4 上下文会话", ["V4."]),
    ("S5 生命周期", ["V5."]),
    ("S6 工具图谱", ["V6."]),
    ("V-Chain 集成链", ["VC"]),
]

lines = [
    "# Codex Engram 记忆单元审计 — 有效性报告",
    "",
    f"日期: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}",
    f"Engram 版本: {version}",
    "验证方式: unit_write.py(阶段1) -> unit_verify.py(阶段3, 新进程)",
    "",
    "## 一、各功能有效性",
    "",
    "| 子系统 | 通过 | 有效性 |",
    "|--------|------|--------|",
]
for group, prefixes in groups:
    passed, total = report_group(group, prefixes)
    valid = "有效" if passed == total else "部分有效"
    lines.append(f"| {group} | {passed}/{total} | {valid} |")

lines.extend([
    "",
    "## 二、逐项结果",
    "",
    status_table(rec.results),
    "",
    "## 三、跨执行持久化评估",
    "",
    f"- Seed 文件: `{SEED_PATH}`",
    f"- 总验证: {rec.pass_count}/{rec.total}",
    f"- 失败: {rec.fail_count}",
    "",
    "## 四、总评 + 发现的问题 + 建议",
    "",
])
if rec.fail_count == 0:
    lines.append("阶段 1 写入的数据在阶段 3 新进程中可完整读取，记忆持久化链路有效。")
else:
    lines.append("存在失败项，请优先查看逐项结果中的 FAIL。")

(RESULTS_DIR / "unit_effectiveness_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
(RESULTS_DIR / "unit_verify_results.json").write_text(json.dumps(rec.summary(), ensure_ascii=False, indent=2), encoding="utf-8")
rec.print_summary()
print(f"Report 已保存: {RESULTS_DIR / 'unit_effectiveness_report.md'}")
print(json.dumps({"phase": 3, "pass": rec.pass_count, "fail": rec.fail_count, "skip": rec.skip_count}, ensure_ascii=False))
