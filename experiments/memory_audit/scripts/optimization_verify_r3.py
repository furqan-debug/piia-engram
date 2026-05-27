from __future__ import annotations

import asyncio
import json
import logging
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
REPORT_PATH = RESULTS_DIR / "optimization_verify_r3_report.md"
JSON_PATH = RESULTS_DIR / "optimization_verify_r3_results.json"

sys.path.insert(0, str(ENGRAM_SRC))

# Suppress expected fragmentation warnings for deliberate isolated temp roots.
logging.getLogger("piia_engram.core").setLevel(logging.ERROR)

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from piia_engram.core import Engram  # noqa: E402


@dataclass
class CaseResult:
    case: str
    check: str
    passed: bool
    detail: str


RESULTS: list[CaseResult] = []
TMPROOT = Path(tempfile.mkdtemp(prefix="engram_opt_verify_r3_"))


def add(case: str, check: str, passed: bool, detail: str) -> None:
    status = "PASS" if passed else "FAIL"
    clean = str(detail).replace("\n", " ")[:700]
    RESULTS.append(CaseResult(case, check, passed, clean))
    print(f"[{status}] {case} {check}: {clean}")


def safe_case(case: str, check: str, func) -> None:
    try:
        passed, detail = func()
        add(case, check, bool(passed), detail)
    except Exception as exc:  # noqa: BLE001 - verification must continue
        add(case, check, False, f"EXCEPTION: {exc}")
        traceback.print_exc()


def root(name: str) -> Path:
    path = TMPROOT / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_mcp_text(result: Any) -> str:
    chunks: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        chunks.append(text if text is not None else str(item))
    return "\n".join(chunks)


def r3_1() -> tuple[bool, str]:
    e = Engram(root("r3_1"))
    e.update_profile({"description": "marker_alpha"}, source_tool="tool_alpha")
    e.update_profile({"description": "marker_beta"}, source_tool="tool_beta")
    p1 = e.get_profile()
    e.update_profile({"description": "marker_alpha"}, source_tool="tool_alpha")
    p2 = e.get_profile()
    desc1 = p1.get("description", "")
    desc2 = p2.get("description", "")
    ok = (
        "marker_alpha" in desc1
        and "marker_beta" in desc1
        and "marker_alpha" in desc2
        and "marker_beta" in desc2
    )
    return ok, f"before={desc1}; after_rewrite={desc2}"


def r3_2() -> tuple[bool, str]:
    e = Engram(root("r3_2"))
    e.update_profile({"description": "cc_marker"}, source_tool="claude_code")
    e.update_profile({"description": "codex_marker"}, source_tool="codex")
    e.update_profile({"description": "cursor_marker"}, source_tool="cursor")
    desc = e.get_profile().get("description", "")
    markers = ("cc_marker", "codex_marker", "cursor_marker")
    ok = all(marker in desc for marker in markers)
    return ok, f"description={desc}; markers_present={[marker in desc for marker in markers]}"


def r3_3() -> tuple[bool, str]:
    e = Engram(root("r3_decisions"))
    d1 = e.add_decision("选择前端框架", choice="React")
    d2 = e.add_decision("选择前端框架", choice="Vue")
    d1_id = d1.get("id", "")
    d2_id = d2.get("id", "")
    d2_related = d2.get("related_ids", [])
    ok = d1_id != d2_id and d2_id not in d2_related and d1_id in d2_related
    return ok, f"d1={json.dumps(d1, ensure_ascii=False)}; d2={json.dumps(d2, ensure_ascii=False)}"


def r3_4() -> tuple[bool, str]:
    e = Engram(root("r3_three_choices"))
    d1 = e.add_decision("选择前端框架", choice="React")
    d2 = e.add_decision("选择前端框架", choice="Vue")
    d3 = e.add_decision("选择前端框架", choice="Svelte")
    d3_id = d3.get("id", "")
    d3_related = d3.get("related_ids", [])
    ok = d3.get("status") != "duplicate" and d3_id not in d3_related
    return ok, f"d1_id={d1.get('id')}; d2_id={d2.get('id')}; d3={json.dumps(d3, ensure_ascii=False)}"


def r3_5() -> tuple[bool, str]:
    e = Engram(root("r3_lessons"))
    l1 = e.add_lesson("Git分支策略最佳实践", domain="workflow")
    l2 = e.add_lesson("Git分支策略最佳实践（补充案例）", domain="workflow")
    l1_id = l1.get("id", "")
    l2_id = l2.get("id", "")
    l2_related = l2.get("related_ids", [])
    ok = l2_id not in l2_related and l1_id in l2_related
    return ok, f"l1={json.dumps(l1, ensure_ascii=False)}; l2={json.dumps(l2, ensure_ascii=False)}"


async def run_doctor_mcp() -> dict[str, Any]:
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

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            if "doctor" not in names:
                return {"ok": False, "detail": f"doctor missing; tools={names}"}
            result = await session.call_tool("doctor", {"output_format": "json"})
            text = parse_mcp_text(result)
            if getattr(result, "isError", False):
                return {"ok": False, "detail": text}
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                return {"ok": False, "detail": f"invalid JSON: {exc}; raw={text[:300]}"}
            checks = data.get("checks")
            return {
                "ok": isinstance(checks, list),
                "detail": f"tool_count={len(names)}; checks={[c.get('name') for c in checks or []]}",
            }


def r3_6() -> tuple[bool, str]:
    result = asyncio.run(run_doctor_mcp())
    return bool(result.get("ok")), str(result.get("detail"))


def write_report() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for item in RESULTS if item.passed)
    failed = len(RESULTS) - passed
    lines = [
        "# v3.29.4 优化验证 (Round 3 — 小回归)",
        "",
        f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "执行者: Codex",
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
        f"通过: {passed}/6",
        f"失败: {failed}",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps({
            "generated_at": datetime.now().isoformat(),
            "tmproot": str(TMPROOT),
            "pass": passed,
            "fail": failed,
            "total": len(RESULTS),
            "results": [item.__dict__ for item in RESULTS],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nReport written: {REPORT_PATH}")
    print(f"JSON written: {JSON_PATH}")
    print(f"Summary: {passed} PASS / {failed} FAIL / {len(RESULTS)} TOTAL")


def main() -> int:
    print(f"TMPROOT={TMPROOT}")
    try:
        safe_case("R3-1", "description 重写不丢 marker", r3_1)
        safe_case("R3-2", "三工具 marker 共存", r3_2)
        safe_case("R3-3", "decision ID 唯一 + 无自指", r3_3)
        safe_case("R3-4", "三方 choice 共存", r3_4)
        safe_case("R3-5", "lesson related 无自指", r3_5)
        safe_case("R3-6", "doctor MCP 回归", r3_6)
    finally:
        shutil.rmtree(TMPROOT, ignore_errors=True)
        write_report()
    return 0 if all(item.passed for item in RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
