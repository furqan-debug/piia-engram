# v3.29.4 优化验证 (Round 3 — 小回归)

日期: 2026-05-27 08:12:54
执行者: Codex

| Case | 检查项 | 结果 | 备注 |
|------|--------|------|------|
| R3-1 | description 重写不丢 marker | PASS | before=marker_alpha marker_beta; after_rewrite=marker_alpha marker_beta |
| R3-2 | 三工具 marker 共存 | PASS | description=cc_marker codex_marker cursor_marker; markers_present=[True, True, True] |
| R3-3 | decision ID 唯一 + 无自指 | PASS | d1={"question": "选择前端框架", "choice": "React", "timestamp": "2026-05-27T08:12:50", "created_at": "2026-05-27T08:12:50", "last_reviewed": "2026-05-27T08:12:50", "id": "8127fdcf901b", "status": "active", "access_count": 0, "tier": "verified", "related_ids": []}; d2={"question": "选择前端框架", "choice": "Vue", "timestamp": "2026-05-27T08:12:50", "created_at": "2026-05-27T08:12:50", "last_reviewed": "2026-05-27T08:12:50", "id": "7eda45d55f5c", "status": "active", "access_count": 0, "tier": "verified", "related_ids": ["8127fdcf901b"], "_dedup_note": "related to 8127fdcf901b (sim=100%)"} |
| R3-4 | 三方 choice 共存 | PASS | d1_id=8127fdcf901b; d2_id=7eda45d55f5c; d3={"question": "选择前端框架", "choice": "Svelte", "timestamp": "2026-05-27T08:12:50", "created_at": "2026-05-27T08:12:50", "last_reviewed": "2026-05-27T08:12:50", "id": "c165df97116e", "status": "active", "access_count": 0, "tier": "verified", "related_ids": ["8127fdcf901b"], "_dedup_note": "related to 8127fdcf901b (sim=100%)"} |
| R3-5 | lesson related 无自指 | PASS | l1={"summary": "Git分支策略最佳实践", "domain": "workflow", "timestamp": "2026-05-27T08:12:50", "created_at": "2026-05-27T08:12:50", "last_reviewed": "2026-05-27T08:12:50", "id": "8ad62adfcdf2", "status": "active", "access_count": 0, "tier": "verified", "related_ids": []}; l2={"summary": "Git分支策略最佳实践（补充案例）", "domain": "workflow", "timestamp": "2026-05-27T08:12:50", "created_at": "2026-05-27T08:12:50", "last_reviewed": "2026-05-27T08:12:50", "id": "5fbab55a787b", "status": "active", "access_count": 0, "tier": "verified", "related_ids": ["8ad62adfcdf2"], "_dedup_note": "related to 8ad62adfcdf2 (sim=80%)"} |
| R3-6 | doctor MCP 回归 | PASS | tool_count=14; checks=['identity_completeness', 'identity_provenance', 'knowledge_volume', 'stale_knowledge', 'near_duplicates', 'decision_conflicts', 'health_score', 'quick_context_freshness'] |

通过: 6/6
失败: 0
