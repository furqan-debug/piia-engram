from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PYTHON = Path("C:/Users/pp3x3/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe")
REPO = Path("E:/Personal Intelligence Identity Asset/engram")
ENGRAM_SRC = REPO / "src"
RESULTS_DIR = REPO / "experiments" / "memory_audit" / "results"
REPORT_PATH = RESULTS_DIR / "optimization_verify_r2_report.md"
JSON_PATH = RESULTS_DIR / "optimization_verify_r2_results.json"

sys.path.insert(0, str(ENGRAM_SRC))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from piia_engram.core import Engram  # noqa: E402
from piia_engram.storage import (  # noqa: E402
    SIMILARITY_DUPLICATE_THRESHOLD,
    SIMILARITY_THRESHOLD,
    STALE_DECAY_MULTIPLIERS,
    _SUPPLEMENT_MARKERS,
)


@dataclass
class CaseResult:
    case: str
    check: str
    passed: bool
    detail: str


RESULTS: list[CaseResult] = []
TMPDIR = Path(tempfile.mkdtemp(prefix="engram_opt_verify_r2_"))
engram = Engram(TMPDIR)


def add(case: str, check: str, passed: bool, detail: str) -> None:
    status = "PASS" if passed else "FAIL"
    clean_detail = str(detail).replace("\n", " ")[:700]
    RESULTS.append(CaseResult(case, check, passed, clean_detail))
    print(f"[{status}] {case} {check}: {clean_detail}")


def safe_case(case: str, check: str, func) -> None:
    try:
        passed, detail = func()
        add(case, check, bool(passed), detail)
    except Exception as exc:  # noqa: BLE001 - audit must continue
        add(case, check, False, f"EXCEPTION: {exc}")
        traceback.print_exc()


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def lesson_by_id(lesson_id: str) -> dict:
    lessons = read_json(TMPDIR / "knowledge" / "lessons.json", [])
    for item in lessons:
        if item.get("id") == lesson_id:
            return item
    raise AssertionError(f"lesson not found: {lesson_id}")


def parse_mcp_text(result: Any) -> str:
    chunks: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        chunks.append(text if text is not None else str(item))
    return "\n".join(chunks)


async def run_mcp_checks() -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ENGRAM_SRC)
    env["ENGRAM_TOOLS"] = "core"
    env["PYTHONIOENCODING"] = "utf-8"

    params = StdioServerParameters(
        command=str(PYTHON),
        args=["-m", "piia_engram.mcp_server"],
        env=env,
        cwd=str(REPO),
    )

    real_engram = Engram()
    profile_path = real_engram.root / "identity" / "profile.json"
    profile_exists = profile_path.exists()
    profile_backup = profile_path.read_bytes() if profile_exists else b""

    out: dict[str, Any] = {}
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]
                out["tool_names"] = tool_names
                out["update_identity_schema"] = next(
                    (tool.inputSchema for tool in tools.tools if tool.name == "update_identity"),
                    None,
                )

                if "doctor" in tool_names:
                    doctor_json_result = await session.call_tool("doctor", {"output_format": "json"})
                    doctor_md_result = await session.call_tool("doctor", {"output_format": "markdown"})
                    out["doctor_json_is_error"] = bool(getattr(doctor_json_result, "isError", False))
                    out["doctor_markdown_is_error"] = bool(getattr(doctor_md_result, "isError", False))
                    out["doctor_json_text"] = parse_mcp_text(doctor_json_result)
                    out["doctor_markdown_text"] = parse_mcp_text(doctor_md_result)
                    if not out["doctor_json_is_error"]:
                        try:
                            out["doctor_json"] = json.loads(out["doctor_json_text"])
                        except json.JSONDecodeError as exc:
                            out["doctor_json_error"] = f"{exc}; raw={out['doctor_json_text'][:300]}"
                    else:
                        out["doctor_error"] = out["doctor_json_text"]
                else:
                    out["doctor_error"] = "doctor tool not exposed in ENGRAM_TOOLS=core"

                if "update_identity" in tool_names:
                    update_result = await session.call_tool(
                        "update_identity",
                        {
                            "field": "profile",
                            "updates_json": json.dumps({"role": "verify_tester"}, ensure_ascii=False),
                            "source_tool": "codex_verify",
                        },
                    )
                    out["update_identity_is_error"] = bool(getattr(update_result, "isError", False))
                    out["update_identity_text"] = parse_mcp_text(update_result)
                    profile_after = Engram().get_profile()
                    out["profile_after_update"] = {
                        "role": profile_after.get("role"),
                        "_last_updated_by": profile_after.get("_last_updated_by"),
                        "role_provenance": (
                            profile_after.get("_provenance", {})
                            .get("role", {})
                        ),
                    }
                else:
                    out["update_identity_error"] = "update_identity tool not exposed"
    finally:
        if profile_exists:
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_bytes(profile_backup)
        elif profile_path.exists():
            profile_path.unlink()

    return out


def ov_1() -> tuple[bool, str]:
    lesson = engram.add_lesson(
        "OV1 R2 identity card side effect sentinel",
        domain="optimization_verify_r2",
        source_tool="codex_verify",
    )
    before = lesson_by_id(lesson["id"]).get("access_count")
    _ = engram.export_identity_card()
    after = lesson_by_id(lesson["id"]).get("access_count")
    return before == after, f"access_count before={before}, after={after}, lesson_id={lesson['id']}"


def ov_2_markers() -> tuple[bool, str]:
    engram.update_profile({"description": "marker_tool_a"}, source_tool="tool_a")
    engram.update_profile({"description": "marker_tool_b"}, source_tool="tool_b")
    desc = engram.get_profile().get("description", "")
    ok = "marker_tool_a" in desc and "marker_tool_b" in desc
    return ok, f"description={desc}"


def ov_2_repeat_no_duplicate() -> tuple[bool, str]:
    engram.update_profile({"description": "marker_tool_a"}, source_tool="tool_a")
    desc = engram.get_profile().get("description", "")
    count_a = desc.split().count("marker_tool_a")
    # The task's gating assertion is "marker_tool_a is not appended twice".
    # Whether marker_tool_b is preserved is reported as a non-blocking observation below.
    ok = count_a == 1
    return ok, f"marker_tool_a count={count_a}; marker_tool_b_present={'marker_tool_b' in desc}; description={desc}"


def ov_3() -> tuple[bool, str]:
    profile = engram.get_profile()
    desc_prov = profile.get("_provenance", {}).get("description", {})
    ok = bool(desc_prov.get("by")) and bool(desc_prov.get("at")) and bool(profile.get("_last_updated_by"))
    return ok, f"description_provenance={desc_prov}; _last_updated_by={profile.get('_last_updated_by')}"


LESSON_STATE: dict[str, Any] = {}
DECISION_STATE: dict[str, Any] = {}


def ov_4_setup() -> None:
    base = engram.add_lesson("Python异步编程中的错误处理最佳实践", domain="python")
    supplement = engram.add_lesson("Python异步编程中的错误处理最佳实践（补充案例）", domain="python")
    duplicate = engram.add_lesson("Python异步编程中的错误处理最佳实践", domain="python")
    unrelated = engram.add_lesson("Go语言并发模式", domain="go")
    boundary = engram.add_lesson("Python异步编程中的错误处理最佳实践（边界情况分析）", domain="python")
    counterexample = engram.add_lesson("Python异步编程中的错误处理最佳实践（反例收集）", domain="python")
    LESSON_STATE.update({
        "base": base,
        "supplement": supplement,
        "duplicate": duplicate,
        "unrelated": unrelated,
        "boundary": boundary,
        "counterexample": counterexample,
    })


def is_related_to_base(item: dict) -> bool:
    base_id = LESSON_STATE["base"].get("id")
    return (
        item.get("status") != "duplicate"
        and "related" in str(item.get("_dedup_note", ""))
        and base_id in (item.get("related_ids") or [])
    )


def ov_4_related(key: str) -> tuple[bool, str]:
    item = LESSON_STATE[key]
    return is_related_to_base(item), json.dumps(item, ensure_ascii=False)


def ov_4_duplicate() -> tuple[bool, str]:
    item = LESSON_STATE["duplicate"]
    return item.get("status") == "duplicate", json.dumps(item, ensure_ascii=False)


def ov_4_unrelated() -> tuple[bool, str]:
    item = LESSON_STATE["unrelated"]
    ok = item.get("status") != "duplicate" and not item.get("_dedup_note")
    return ok, json.dumps(item, ensure_ascii=False)


def ov_5_setup() -> None:
    first = engram.add_decision("选择前端框架", choice="React")
    different_choice = engram.add_decision("选择前端框架", choice="Vue")
    unrelated = engram.add_decision("选择数据库引擎", choice="PostgreSQL")
    DECISION_STATE.update({
        "first": first,
        "different_choice": different_choice,
        "unrelated": unrelated,
    })


def ov_5_different_choice_related() -> tuple[bool, str]:
    item = DECISION_STATE["different_choice"]
    ok = (
        item.get("status") != "duplicate"
        and (bool(item.get("_dedup_note")) or bool(item.get("related_ids")))
    )
    return ok, json.dumps(item, ensure_ascii=False)


def ov_5_unrelated() -> tuple[bool, str]:
    item = DECISION_STATE["unrelated"]
    ok = item.get("status") != "duplicate" and not item.get("_dedup_note")
    return ok, json.dumps(item, ensure_ascii=False)


def ov_6_1() -> tuple[bool, str]:
    return SIMILARITY_DUPLICATE_THRESHOLD == 0.95, f"SIMILARITY_DUPLICATE_THRESHOLD={SIMILARITY_DUPLICATE_THRESHOLD}"


def ov_6_2() -> tuple[bool, str]:
    return SIMILARITY_THRESHOLD == 0.55, f"SIMILARITY_THRESHOLD={SIMILARITY_THRESHOLD}"


def ov_6_3() -> tuple[bool, str]:
    required = {"补充", "案例", "反例", "边界", "edge case"}
    present = set(_SUPPLEMENT_MARKERS)
    return required.issubset(present), f"required={sorted(required)}; present_subset={sorted(required & present)}"


def ov_7_keys() -> tuple[bool, str]:
    required = {"user_preference", "debug", "default"}
    present = set(STALE_DECAY_MULTIPLIERS)
    return required.issubset(present), f"keys={sorted(present)}"


def ov_7_value(key: str, expected: float) -> tuple[bool, str]:
    actual = STALE_DECAY_MULTIPLIERS.get(key)
    return actual == expected, f"{key}={actual}, expected={expected}"


def ov_8(mcp_result: dict[str, Any]) -> tuple[bool, str]:
    doctor_data = mcp_result.get("doctor_json")
    markdown = mcp_result.get("doctor_markdown_text", "")
    if not isinstance(doctor_data, dict):
        return False, f"doctor unavailable: {mcp_result.get('doctor_error') or mcp_result.get('doctor_json_error') or mcp_result.get('mcp_error')}"
    checks = doctor_data.get("checks")
    names = {c.get("name") for c in checks or [] if isinstance(c, dict)}
    ok = (
        not mcp_result.get("doctor_json_is_error")
        and not mcp_result.get("doctor_markdown_is_error")
        and isinstance(checks, list)
        and {"identity_completeness", "health_score", "stale_knowledge"}.issubset(names)
        and "| 检查项 |" in markdown
    )
    return ok, f"checks={sorted(names)}; markdown_table={'| 检查项 |' in markdown}"


def ov_8_4(mcp_result: dict[str, Any]) -> tuple[bool, str]:
    tool_names = set(mcp_result.get("tool_names") or [])
    return "doctor" in tool_names, f"ENGRAM_TOOLS=core tool_count={len(tool_names)}; doctor_present={'doctor' in tool_names}"


def ov_9(mcp_result: dict[str, Any]) -> tuple[bool, str]:
    profile = mcp_result.get("profile_after_update") or {}
    schema = mcp_result.get("update_identity_schema") or {}
    has_source_tool = "source_tool" in (schema.get("properties") or {})
    ok = (
        not mcp_result.get("update_identity_is_error")
        and has_source_tool
        and profile.get("_last_updated_by") == "codex_verify"
        and (profile.get("role_provenance") or {}).get("by") == "codex_verify"
    )
    return ok, f"schema_has_source_tool={has_source_tool}; profile_after_update={profile}"


def ov_10() -> tuple[bool, str]:
    path = REPO / "docs" / "cross-tool-guide.md"
    if not path.exists():
        return False, f"missing: {path}"
    text = path.read_text(encoding="utf-8")
    checks = {
        "跨工具": "跨工具" in text,
        "跨会话": "跨会话" in text,
        "doctor": "doctor" in text.lower(),
    }
    return all(checks.values()), f"path={path}; checks={checks}"


def read_project_version() -> str:
    try:
        import tomllib

        data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
        return str(data.get("project", {}).get("version", "unknown"))
    except Exception:
        return "unknown"


def write_report() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in RESULTS if r.passed)
    failed = len(RESULTS) - passed
    version = read_project_version()
    ov42 = next((r for r in RESULTS if r.case == "OV-4.2"), None)
    ov8 = next((r for r in RESULTS if r.case == "OV-8"), None)

    lines = [
        "# v3.29.4 优化验证报告 (Round 2)",
        "",
        f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "执行者: Codex",
        "背景: Round 1 两个 FAIL 已修复，本轮全量回归验证",
        f"Engram 版本: {version}",
        f"临时目录: `{TMPDIR}`（脚本结束后已清理）",
        "",
        "## 验证结果",
        "",
        "| Case | 检查项 | 结果 | 备注 |",
        "|------|--------|------|------|",
    ]
    for item in RESULTS:
        status = "PASS" if item.passed else "FAIL"
        detail = item.detail.replace("|", "\\|")
        lines.append(f"| {item.case} | {item.check} | {status} | {detail} |")

    lines.extend([
        "",
        "## Round 1 FAIL 修复状态",
        "",
        "| FAIL 项 | 原因 | 修复内容 | Round 2 状态 |",
        "|---------|------|----------|-------------|",
        f"| OV-4.2 | sim=0.88 > 0.85 阈值 | 阈值提高到 0.95 + 补充词检测 | {'PASS' if ov42 and ov42.passed else 'FAIL'} |",
        f"| OV-8 | knowledge_overview 方法不存在 | 改为 get_knowledge_overview | {'PASS' if ov8 and ov8.passed else 'FAIL'} |",
        "",
        "## 非阻断观察",
        "",
        "- OV-2.4 严格按任务只判定 `marker_tool_a` 未重复追加；当前 detail 中也会显示重复写后 `marker_tool_b` 是否仍存在。",
        "- OV-5.2 严格按任务只判定不同 choice 未被 duplicate 丢弃，并存在关联信息；detail 中可继续观察 related_ids 是否指向自身。",
        "",
        "## 总结",
        "",
        f"通过: {passed}/{len(RESULTS)}",
        f"失败: {failed}",
    ])

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps({
            "generated_at": datetime.now().isoformat(),
            "version": version,
            "tmpdir": str(TMPDIR),
            "pass": passed,
            "fail": failed,
            "total": len(RESULTS),
            "round1_fixes": {
                "OV-4.2": bool(ov42 and ov42.passed),
                "OV-8": bool(ov8 and ov8.passed),
            },
            "results": [item.__dict__ for item in RESULTS],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nReport written: {REPORT_PATH}")
    print(f"JSON written: {JSON_PATH}")
    print(f"Summary: {passed} PASS / {failed} FAIL / {len(RESULTS)} TOTAL")


def main() -> int:
    print(f"TMPDIR={TMPDIR}")
    mcp_result: dict[str, Any] = {}
    try:
        safe_case("OV-1", "export_identity_card 不更新 access_count", ov_1)
        safe_case("OV-2.3", "description 同时保留 tool_a/tool_b marker", ov_2_markers)
        safe_case("OV-2.4", "重复 description marker 不重复追加", ov_2_repeat_no_duplicate)
        safe_case("OV-3", "profile 字段级溯源字段存在", ov_3)

        try:
            ov_4_setup()
        except Exception:
            traceback.print_exc()
        safe_case("OV-4.2", "lesson 补充案例走 related 而非 duplicate", lambda: ov_4_related("supplement"))
        safe_case("OV-4.3", "lesson 精确重复层返回 duplicate", ov_4_duplicate)
        safe_case("OV-4.4", "lesson 无关内容正常通过", ov_4_unrelated)
        safe_case("OV-4.5", "lesson 边界情况走 related", lambda: ov_4_related("boundary"))
        safe_case("OV-4.6", "lesson 反例收集走 related", lambda: ov_4_related("counterexample"))

        try:
            ov_5_setup()
        except Exception:
            traceback.print_exc()
        safe_case("OV-5.2", "decision 同问题不同 choice 保留并关联", ov_5_different_choice_related)
        safe_case("OV-5.3", "decision 无关问题正常通过", ov_5_unrelated)

        safe_case("OV-6.1", "SIMILARITY_DUPLICATE_THRESHOLD == 0.95", ov_6_1)
        safe_case("OV-6.2", "SIMILARITY_THRESHOLD == 0.55", ov_6_2)
        safe_case("OV-6.3", "_SUPPLEMENT_MARKERS 包含关键补充词", ov_6_3)

        safe_case("OV-7.1", "STALE_DECAY_MULTIPLIERS 包含必需 key", ov_7_keys)
        safe_case("OV-7.2", "user_preference multiplier == 3.0", lambda: ov_7_value("user_preference", 3.0))
        safe_case("OV-7.3", "debug multiplier == 0.5", lambda: ov_7_value("debug", 0.5))
        safe_case("OV-7.4", "default multiplier == 1.0", lambda: ov_7_value("default", 1.0))

        try:
            mcp_result = asyncio.run(run_mcp_checks())
        except Exception as exc:  # noqa: BLE001
            mcp_result = {"mcp_error": str(exc)}
            traceback.print_exc()
        safe_case("OV-8", "doctor MCP JSON/Markdown 输出结构", lambda: ov_8(mcp_result))
        safe_case("OV-8.4", "doctor 在 ENGRAM_TOOLS=core 中可用", lambda: ov_8_4(mcp_result))
        safe_case("OV-9", "update_identity MCP source_tool 溯源并恢复 profile", lambda: ov_9(mcp_result))
        safe_case("OV-10", "docs/cross-tool-guide.md 存在且含关键内容", ov_10)
    finally:
        shutil.rmtree(TMPDIR, ignore_errors=True)
        write_report()

    return 0 if all(r.passed for r in RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
