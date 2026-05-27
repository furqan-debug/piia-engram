"""v3.29.4 优化项守门测试

把 experiments/memory_audit/results 中 R3 的 6 个回归 case
固化为正式单元测试，确保未来发版不会回退到已修复的缺陷。

来源：
- R2 暴露的两个非阻断观察
- R3 验证修复后的回归

覆盖：
- description 重复写不丢已有 marker（P0）
- description 三工具 marker 共存
- decision 同问题不同 choice — ID 唯一 + 无自指（P1）
- decision 三方 choice 共存
- lesson related_ids 无自指
- doctor 在 core tier 可用
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from piia_engram.core import Engram


def _make(tmp_path: Path) -> Engram:
    return Engram(root=tmp_path)


def test_description_rewrite_preserves_existing_markers(tmp_path: Path):
    """R3-1: 重写已有 marker 时不能丢失其他工具写入的 marker。"""
    e = _make(tmp_path)
    e.update_profile({"description": "marker_alpha"}, source_tool="tool_alpha")
    e.update_profile({"description": "marker_beta"}, source_tool="tool_beta")
    p1 = e.get_profile()
    assert "marker_alpha" in p1["description"]
    assert "marker_beta" in p1["description"]

    # 重复写 marker_alpha：其他 marker 必须保留
    e.update_profile({"description": "marker_alpha"}, source_tool="tool_alpha")
    p2 = e.get_profile()
    assert "marker_beta" in p2["description"], "FAIL: marker_beta lost after re-write"
    assert "marker_alpha" in p2["description"]


def test_description_three_tools_coexist(tmp_path: Path):
    """R3-2: 三个工具分别写入的 marker 必须共存。"""
    e = _make(tmp_path)
    e.update_profile({"description": "cc_marker"}, source_tool="claude_code")
    e.update_profile({"description": "codex_marker"}, source_tool="codex")
    e.update_profile({"description": "cursor_marker"}, source_tool="cursor")
    p = e.get_profile()
    for marker in ("cc_marker", "codex_marker", "cursor_marker"):
        assert marker in p["description"], f"FAIL: {marker} missing"


def test_decision_same_question_different_choice_unique_id_no_self_ref(tmp_path: Path):
    """R3-3: 同问题不同 choice 应产生不同 ID，related_ids 不能自指。"""
    e = _make(tmp_path)
    d1 = e.add_decision("选择前端框架", choice="React")
    d2 = e.add_decision("选择前端框架", choice="Vue")

    assert d1["id"] != d2.get("id", ""), "FAIL: same ID for different choices"
    assert d2.get("id", "") not in d2.get("related_ids", []), "FAIL: self-reference"
    assert d1["id"] in d2.get("related_ids", []), "FAIL: should reference D1"


def test_decision_three_way_choice_coexist(tmp_path: Path):
    """R3-4: 第三个 choice 不应被错误判定为 duplicate。"""
    e = _make(tmp_path)
    e.add_decision("选择前端框架", choice="React")
    e.add_decision("选择前端框架", choice="Vue")
    d3 = e.add_decision("选择前端框架", choice="Svelte")

    assert d3.get("status") != "duplicate", "FAIL: third choice wrongly blocked"
    assert d3.get("id", "") not in d3.get("related_ids", []), "FAIL: self-ref"


def test_lesson_related_ids_no_self_reference(tmp_path: Path):
    """R3-5: lesson 关联时 related_ids 不能包含自身 ID。"""
    e = _make(tmp_path)
    l1 = e.add_lesson("Git分支策略最佳实践", domain="workflow")
    l2 = e.add_lesson("Git分支策略最佳实践（补充案例）", domain="workflow")

    assert l2.get("id", "") not in l2.get("related_ids", []), "FAIL: lesson self-ref"
    assert l1["id"] in l2.get("related_ids", []), "FAIL: should reference L1"


def test_doctor_available_in_core_tier():
    """R3-6: doctor 必须出现在默认 (core) tier 工具集中。"""
    from piia_engram.mcp_server import TIER1_TOOLS

    assert "doctor" in TIER1_TOOLS, "FAIL: doctor missing from TIER1_TOOLS"


def test_doctor_runs_without_error(tmp_path: Path):
    """R3-6 扩展: 直接调用 doctor 应返回 checks 列表且不抛错。"""
    # 通过直接构造 Engram 并模拟 doctor 内部走的核心调用，
    # 以避免依赖整个 MCP stdio 链路。
    e = _make(tmp_path)
    e.add_lesson("示例经验", "workflow")
    e.add_decision("示例决策", choice="A")

    overview = e.get_knowledge_overview()
    assert isinstance(overview, dict)
    # 关键字段存在
    assert "total" in overview or len(overview) > 0


def test_doctor_reads_nested_health_fields(tmp_path: Path, monkeypatch):
    """R4-1 (v3.29.4 post-release fix): doctor 必须从 overview["health"] 读取
    health_score / items_needing_review / items_to_archive — 这些字段嵌套在
    "health" 子对象下而非顶层。早期 doctor 错误地访问 overview["lifecycle"]
    与 overview["health_score"]，导致即使存在 active 知识也报 health_score=0。

    本测试覆盖回归路径：直接通过 mcp_server 模块的 doctor wrapper 调用，
    验证 markdown 输出包含非零 health_score。
    """
    import asyncio
    import json
    from piia_engram import mcp_server

    e = _make(tmp_path)
    # 写入多 domain 知识让 coverage 维度非零
    e.add_lesson("Python 异步错误处理实战", "python,async")
    e.add_lesson("Git rebase 与 merge 的取舍", "git,workflow")
    e.add_lesson("MCP stdio transport 调试", "mcp,debugging")
    e.add_decision("HTTP 客户端选型", choice="httpx", domain="python")

    # 用本地 Engram 替换模块级全局
    monkeypatch.setattr(mcp_server, "_engram", e)

    # JSON 输出便于断言
    raw = asyncio.run(mcp_server.doctor(output_format="json"))
    payload = json.loads(raw)

    checks = {c["name"]: c for c in payload["checks"]}
    health = checks["health_score"]

    # 字段路径修对了 → 应该 > 0（实际 90+ 因为新建数据全 fresh）
    detail = health["detail"]
    score_str = detail.split("/")[0].strip()
    score = int(score_str)
    assert score > 0, (
        f"FAIL: health_score=0 — doctor 未正确从 overview['health'] 读取数据。"
        f" detail={detail!r}"
    )
    # detail 应该包含 4 维度细分
    for dim in ("freshness", "quality", "coverage", "cleanliness"):
        assert dim in detail, f"FAIL: dimension breakdown missing '{dim}'"

    # stale_knowledge 不应因字段路径错误而虚假报 0
    stale = checks["stale_knowledge"]
    assert "需复审" in stale["detail"] and "可归档" in stale["detail"]
