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
REPORT_PATH = RESULTS_DIR / "optimization_verify_report.md"
JSON_PATH = RESULTS_DIR / "optimization_verify_results.json"

sys.path.insert(0, str(ENGRAM_SRC))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from piia_engram.core import Engram  # noqa: E402
from piia_engram.storage import (  # noqa: E402
    SIMILARITY_DUPLICATE_THRESHOLD,
    SIMILARITY_THRESHOLD,
    STALE_DECAY_MULTIPLIERS,
)


@dataclass
class CaseResult:
    case: str
    check: str
    passed: bool
    detail: str


RESULTS: list[CaseResult] = []
TMPDIR = Path(tempfile.mkdtemp(prefix="engram_opt_verify_"))
engram = Engram(TMPDIR)


def add(case: str, check: str, passed: bool, detail: str) -> None:
    status = "PASS" if passed else "FAIL"
    detail = str(detail).replace("\n", " ")[:500]
    RESULTS.append(CaseResult(case, check, passed, detail))
    print(f"[{status}] {case} {check}: {detail}")


def safe_case(case: str, check: str, func) -> None:
    try:
        passed, detail = func()
        add(case, check, bool(passed), detail)
    except Exception as exc:  # noqa: BLE001 - audit must continue after each failure
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
        if text is not None:
            chunks.append(text)
        else:
            chunks.append(str(item))
    return "\n".join(chunks)


async def run_mcp_checks() -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ENGRAM_SRC)
    env["ENGRAM_TOOLS"] = "all"
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

                if "doctor" not in tool_names:
                    out["doctor_error"] = "doctor tool not exposed by MCP server"
                else:
                    doctor_json_result = await session.call_tool("doctor", {"output_format": "json"})
                    doctor_md_result = await session.call_tool("doctor", {"output_format": "markdown"})
                    out["doctor_json_is_error"] = bool(getattr(doctor_json_result, "isError", False))
                    out["doctor_markdown_is_error"] = bool(getattr(doctor_md_result, "isError", False))
                    doctor_json_text = parse_mcp_text(doctor_json_result)
                    doctor_md_text = parse_mcp_text(doctor_md_result)
                    out["doctor_json_text"] = doctor_json_text
                    out["doctor_markdown_text"] = doctor_md_text
                    if out["doctor_json_is_error"] or out["doctor_markdown_is_error"]:
                        out["doctor_error"] = doctor_json_text or doctor_md_text
                    else:
                        try:
                            out["doctor_json"] = json.loads(doctor_json_text)
                        except json.JSONDecodeError as exc:
                            out["doctor_json_error"] = f"{exc}; raw={doctor_json_text[:300]}"

                if "update_identity" not in tool_names:
                    out["update_identity_error"] = "update_identity tool not exposed by MCP server"
                else:
                    update_text = parse_mcp_text(await session.call_tool(
                        "update_identity",
                        {
                            "field": "profile",
                            "updates_json": json.dumps({"role": "verify_tester"}, ensure_ascii=False),
                            "source_tool": "codex_verify",
                        },
                    ))
                    out["update_identity_text"] = update_text
                    try:
                        out["update_identity_json"] = json.loads(update_text)
                    except json.JSONDecodeError:
                        out["update_identity_json"] = None

                    profile_after = Engram().get_profile()
                    out["profile_after_update"] = {
                        "role": profile_after.get("role"),
                        "_last_updated_by": profile_after.get("_last_updated_by"),
                        "role_provenance": (
                            profile_after.get("_provenance", {})
                            .get("role", {})
                        ),
                    }
    finally:
        if profile_exists:
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_bytes(profile_backup)
        elif profile_path.exists():
            profile_path.unlink()

    return out


def ov_1() -> tuple[bool, str]:
    lesson = engram.add_lesson(
        "OV1 identity card side effect sentinel",
        domain="optimization_verify",
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


def ov_2_no_duplicate() -> tuple[bool, str]:
    engram.update_profile({"description": "marker_tool_a"}, source_tool="tool_a")
    desc = engram.get_profile().get("description", "")
    count = desc.split().count("marker_tool_a")
    return count == 1, f"marker_tool_a count={count}; description={desc}"


def ov_3() -> tuple[bool, str]:
    profile = engram.get_profile()
    provenance = profile.get("_provenance", {})
    desc_prov = provenance.get("description", {})
    ok = bool(desc_prov.get("by")) and bool(desc_prov.get("at")) and bool(profile.get("_last_updated_by"))
    return ok, f"description_provenance={desc_prov}; _last_updated_by={profile.get('_last_updated_by')}"


LESSON_RELATED: dict[str, Any] = {}
DECISION_RELATED: dict[str, Any] = {}


def ov_4_setup() -> None:
    first = engram.add_lesson("Python异步编程中的错误处理最佳实践", domain="python")
    related = engram.add_lesson("Python异步编程中的错误处理最佳实践（补充案例）", domain="python")
    duplicate = engram.add_lesson("Python异步编程中的错误处理最佳实践", domain="python")
    unrelated = engram.add_lesson("Go语言并发模式", domain="go")
    LESSON_RELATED.update({
        "first": first,
        "related": related,
        "duplicate": duplicate,
        "unrelated": unrelated,
    })


def ov_4_related() -> tuple[bool, str]:
    related = LESSON_RELATED["related"]
    ok = bool(related.get("_dedup_note")) and bool(related.get("related_ids"))
    return ok, json.dumps(related, ensure_ascii=False)


def ov_4_duplicate() -> tuple[bool, str]:
    duplicate = LESSON_RELATED["duplicate"]
    return duplicate.get("status") == "duplicate", json.dumps(duplicate, ensure_ascii=False)


def ov_4_unrelated() -> tuple[bool, str]:
    unrelated = LESSON_RELATED["unrelated"]
    ok = unrelated.get("status") != "duplicate" and not unrelated.get("_dedup_note")
    return ok, json.dumps(unrelated, ensure_ascii=False)


def ov_5_setup() -> None:
    first = engram.add_decision("选择前端框架", choice="React")
    related_or_dup = engram.add_decision("选择前端框架", choice="Vue")
    unrelated = engram.add_decision("选择数据库引擎", choice="PostgreSQL")
    DECISION_RELATED.update({
        "first": first,
        "related_or_dup": related_or_dup,
        "unrelated": unrelated,
    })


def ov_5_related_or_duplicate() -> tuple[bool, str]:
    item = DECISION_RELATED["related_or_dup"]
    ok = (
        item.get("status") == "duplicate"
        or bool(item.get("_dedup_note"))
        or bool(item.get("related_ids"))
    )
    return ok, json.dumps(item, ensure_ascii=False)


def ov_5_unrelated() -> tuple[bool, str]:
    item = DECISION_RELATED["unrelated"]
    ok = item.get("status") != "duplicate" and not item.get("_dedup_note")
    return ok, json.dumps(item, ensure_ascii=False)


def ov_6_dup_threshold() -> tuple[bool, str]:
    return SIMILARITY_DUPLICATE_THRESHOLD == 0.85, f"SIMILARITY_DUPLICATE_THRESHOLD={SIMILARITY_DUPLICATE_THRESHOLD}"


def ov_6_threshold() -> tuple[bool, str]:
    return SIMILARITY_THRESHOLD == 0.55, f"SIMILARITY_THRESHOLD={SIMILARITY_THRESHOLD}"


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
        return False, f"doctor MCP failed: {mcp_result.get('doctor_error') or mcp_result.get('doctor_json_error') or mcp_result.get('mcp_error')}"
    checks = doctor_data.get("checks")
    names = {c.get("name") for c in checks or [] if isinstance(c, dict)}
    ok = (
        isinstance(checks, list)
        and "identity_completeness" in names
        and "health_score" in names
        and "| 检查项 |" in markdown
    )
    return ok, f"checks={sorted(names)}; markdown_table={'| 检查项 |' in markdown}"


def ov_9(mcp_result: dict[str, Any]) -> tuple[bool, str]:
    profile = mcp_result.get("profile_after_update") or {}
    schema = mcp_result.get("update_identity_schema") or {}
    has_source_tool = "source_tool" in (schema.get("properties") or {})
    ok = (
        has_source_tool
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

    lines = [
        "# v3.29.4 优化验证报告",
        "",
        f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "执行者: Codex",
        f"Engram 版本: {version}（任务目标: 3.29.4+）",
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
        "## 总结",
        "",
        f"通过: {passed}/{len(RESULTS)}",
        f"失败: {failed}",
    ])

    if version != "3.29.4":
        lines.extend([
            "",
            "## 备注",
            "",
            f"- `pyproject.toml` 当前版本号是 `{version}`，任务标题为 `v3.29.4`，版本号本身未列入 18 项判定。",
            "- OV-8/OV-9 通过 MCP stdio transport 调用，并设置 `ENGRAM_TOOLS=all` 暴露完整工具集。",
            "- OV-9 会临时写入真实 profile；脚本在验证后恢复了原始 `profile.json` 文件内容。",
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
            "results": [item.__dict__ for item in RESULTS],
            "note": "OV-8/OV-9 MCP raw details are intentionally summarized in the Markdown report.",
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
        safe_case("OV-2.5", "重复 description marker 不重复追加", ov_2_no_duplicate)
        safe_case("OV-3", "profile 字段级溯源字段存在", ov_3)

        try:
            ov_4_setup()
        except Exception:
            traceback.print_exc()
        safe_case("OV-4.2", "lesson 语义相似层产生 related_ids", ov_4_related)
        safe_case("OV-4.3", "lesson 精确重复层返回 duplicate", ov_4_duplicate)
        safe_case("OV-4.4", "lesson 无关内容正常通过", ov_4_unrelated)

        try:
            ov_5_setup()
        except Exception:
            traceback.print_exc()
        safe_case("OV-5.2", "decision 相似问题触发 duplicate 或 related", ov_5_related_or_duplicate)
        safe_case("OV-5.3", "decision 无关问题正常通过", ov_5_unrelated)

        safe_case("OV-6.1", "SIMILARITY_DUPLICATE_THRESHOLD == 0.85", ov_6_dup_threshold)
        safe_case("OV-6.2", "SIMILARITY_THRESHOLD == 0.55", ov_6_threshold)
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
        safe_case("OV-9", "update_identity MCP source_tool 溯源", lambda: ov_9(mcp_result))
        safe_case("OV-10", "docs/cross-tool-guide.md 存在且含关键内容", ov_10)
    finally:
        shutil.rmtree(TMPDIR, ignore_errors=True)
        write_report()

    return 0 if all(r.passed for r in RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
