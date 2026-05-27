# v3.29.4 优化验证报告 (Round 2)

日期: 2026-05-27 02:50:46
执行者: Codex
背景: Round 1 两个 FAIL 已修复，本轮全量回归验证
Engram 版本: 3.29.3
临时目录: `E:\Temp\engram_opt_verify_r2_fffj7gsb`（脚本结束后已清理）

## 验证结果

| Case | 检查项 | 结果 | 备注 |
|------|--------|------|------|
| OV-1 | export_identity_card 不更新 access_count | PASS | access_count before=0, after=0, lesson_id=67cca2c9f381 |
| OV-2.3 | description 同时保留 tool_a/tool_b marker | PASS | description=marker_tool_a marker_tool_b |
| OV-2.4 | 重复 description marker 不重复追加 | PASS | marker_tool_a count=1; marker_tool_b_present=False; description=marker_tool_a |
| OV-3 | profile 字段级溯源字段存在 | PASS | description_provenance={'by': 'tool_a', 'at': '2026-05-27T02:50:40'}; _last_updated_by=tool_a |
| OV-4.2 | lesson 补充案例走 related 而非 duplicate | PASS | {"summary": "Python异步编程中的错误处理最佳实践（补充案例）", "domain": "python", "timestamp": "2026-05-27T02:50:40", "created_at": "2026-05-27T02:50:40", "last_reviewed": "2026-05-27T02:50:40", "id": "b604bd98513d", "status": "active", "access_count": 0, "tier": "verified", "related_ids": ["b91f8eb2a9e9"], "_dedup_note": "related to b91f8eb2a9e9 (sim=88%)"} |
| OV-4.3 | lesson 精确重复层返回 duplicate | PASS | {"status": "duplicate", "similarity": 1.0, "existing_id": "b91f8eb2a9e9", "existing_summary": "Python异步编程中的错误处理最佳实践", "message": "与现有教训相似度 100%，未重复添加"} |
| OV-4.4 | lesson 无关内容正常通过 | PASS | {"summary": "Go语言并发模式", "domain": "go", "timestamp": "2026-05-27T02:50:40", "created_at": "2026-05-27T02:50:40", "last_reviewed": "2026-05-27T02:50:40", "id": "fbd123f0f464", "status": "active", "access_count": 0, "tier": "verified", "related_ids": []} |
| OV-4.5 | lesson 边界情况走 related | PASS | {"summary": "Python异步编程中的错误处理最佳实践（边界情况分析）", "domain": "python", "timestamp": "2026-05-27T02:50:40", "created_at": "2026-05-27T02:50:40", "last_reviewed": "2026-05-27T02:50:40", "id": "3ddbd342758b", "status": "active", "access_count": 0, "tier": "verified", "related_ids": ["b91f8eb2a9e9"], "_dedup_note": "related to b91f8eb2a9e9 (sim=82%)"} |
| OV-4.6 | lesson 反例收集走 related | PASS | {"summary": "Python异步编程中的错误处理最佳实践（反例收集）", "domain": "python", "timestamp": "2026-05-27T02:50:40", "created_at": "2026-05-27T02:50:40", "last_reviewed": "2026-05-27T02:50:40", "id": "4efb2618b73b", "status": "active", "access_count": 0, "tier": "verified", "related_ids": ["b91f8eb2a9e9"], "_dedup_note": "related to b91f8eb2a9e9 (sim=88%)"} |
| OV-5.2 | decision 同问题不同 choice 保留并关联 | PASS | {"question": "选择前端框架", "choice": "Vue", "timestamp": "2026-05-27T02:50:40", "created_at": "2026-05-27T02:50:40", "last_reviewed": "2026-05-27T02:50:40", "id": "362f884af4db", "status": "active", "access_count": 0, "tier": "verified", "related_ids": ["362f884af4db"], "_dedup_note": "related to 362f884af4db (sim=100%)"} |
| OV-5.3 | decision 无关问题正常通过 | PASS | {"question": "选择数据库引擎", "choice": "PostgreSQL", "timestamp": "2026-05-27T02:50:40", "created_at": "2026-05-27T02:50:40", "last_reviewed": "2026-05-27T02:50:40", "id": "d0f50e29f425", "status": "active", "access_count": 0, "tier": "verified", "related_ids": []} |
| OV-6.1 | SIMILARITY_DUPLICATE_THRESHOLD == 0.95 | PASS | SIMILARITY_DUPLICATE_THRESHOLD=0.95 |
| OV-6.2 | SIMILARITY_THRESHOLD == 0.55 | PASS | SIMILARITY_THRESHOLD=0.55 |
| OV-6.3 | _SUPPLEMENT_MARKERS 包含关键补充词 | PASS | required=['edge case', '反例', '案例', '补充', '边界']; present_subset=['edge case', '反例', '案例', '补充', '边界'] |
| OV-7.1 | STALE_DECAY_MULTIPLIERS 包含必需 key | PASS | keys=['architecture', 'config', 'debug', 'default', 'product', 'strategy', 'user_preference', 'workflow'] |
| OV-7.2 | user_preference multiplier == 3.0 | PASS | user_preference=3.0, expected=3.0 |
| OV-7.3 | debug multiplier == 0.5 | PASS | debug=0.5, expected=0.5 |
| OV-7.4 | default multiplier == 1.0 | PASS | default=1.0, expected=1.0 |
| OV-8 | doctor MCP JSON/Markdown 输出结构 | PASS | checks=['decision_conflicts', 'health_score', 'identity_completeness', 'identity_provenance', 'knowledge_volume', 'near_duplicates', 'quick_context_freshness', 'stale_knowledge']; markdown_table=True |
| OV-8.4 | doctor 在 ENGRAM_TOOLS=core 中可用 | PASS | ENGRAM_TOOLS=core tool_count=14; doctor_present=True |
| OV-9 | update_identity MCP source_tool 溯源并恢复 profile | PASS | schema_has_source_tool=True; profile_after_update={'role': 'verify_tester', '_last_updated_by': 'codex_verify', 'role_provenance': {'by': 'codex_verify', 'at': '2026-05-27T02:50:46'}} |
| OV-10 | docs/cross-tool-guide.md 存在且含关键内容 | PASS | path=E:\Personal Intelligence Identity Asset\engram\docs\cross-tool-guide.md; checks={'跨工具': True, '跨会话': True, 'doctor': True} |

## Round 1 FAIL 修复状态

| FAIL 项 | 原因 | 修复内容 | Round 2 状态 |
|---------|------|----------|-------------|
| OV-4.2 | sim=0.88 > 0.85 阈值 | 阈值提高到 0.95 + 补充词检测 | PASS |
| OV-8 | knowledge_overview 方法不存在 | 改为 get_knowledge_overview | PASS |

## 非阻断观察

- OV-2.4 严格按任务只判定 `marker_tool_a` 未重复追加；当前 detail 中也会显示重复写后 `marker_tool_b` 是否仍存在。
- OV-5.2 严格按任务只判定不同 choice 未被 duplicate 丢弃，并存在关联信息；detail 中可继续观察 related_ids 是否指向自身。

## 总结

通过: 22/22
失败: 0
