# v3.29.4 优化验证报告

日期: 2026-05-27 02:28:24
执行者: Codex
Engram 版本: 3.29.3（任务目标: 3.29.4+）
临时目录: `E:\Temp\engram_opt_verify_r6jgbokv`（脚本结束后已清理）

## 验证结果

| Case | 检查项 | 结果 | 备注 |
|------|--------|------|------|
| OV-1 | export_identity_card 不更新 access_count | PASS | access_count before=0, after=0, lesson_id=c36336c5e09d |
| OV-2.3 | description 同时保留 tool_a/tool_b marker | PASS | description=marker_tool_a marker_tool_b |
| OV-2.5 | 重复 description marker 不重复追加 | PASS | marker_tool_a count=1; description=marker_tool_a |
| OV-3 | profile 字段级溯源字段存在 | PASS | description_provenance={'by': 'tool_a', 'at': '2026-05-27T02:28:21'}; _last_updated_by=tool_a |
| OV-4.2 | lesson 语义相似层产生 related_ids | FAIL | {"status": "duplicate", "similarity": 0.88, "existing_id": "e1c948ad6600", "existing_summary": "Python异步编程中的错误处理最佳实践", "message": "与现有教训相似度 88%，未重复添加"} |
| OV-4.3 | lesson 精确重复层返回 duplicate | PASS | {"status": "duplicate", "similarity": 1.0, "existing_id": "e1c948ad6600", "existing_summary": "Python异步编程中的错误处理最佳实践", "message": "与现有教训相似度 100%，未重复添加"} |
| OV-4.4 | lesson 无关内容正常通过 | PASS | {"summary": "Go语言并发模式", "domain": "go", "timestamp": "2026-05-27T02:28:21", "created_at": "2026-05-27T02:28:21", "last_reviewed": "2026-05-27T02:28:21", "id": "286adf972227", "status": "active", "access_count": 0, "tier": "verified", "related_ids": []} |
| OV-5.2 | decision 相似问题触发 duplicate 或 related | PASS | {"status": "duplicate", "similarity": 1.0, "existing_id": "fdc4059c7b5a", "existing_title": "选择前端框架", "message": "与现有决策相似度 100%，未重复添加"} |
| OV-5.3 | decision 无关问题正常通过 | PASS | {"question": "选择数据库引擎", "choice": "PostgreSQL", "timestamp": "2026-05-27T02:28:21", "created_at": "2026-05-27T02:28:21", "last_reviewed": "2026-05-27T02:28:21", "id": "08a82e873e42", "status": "active", "access_count": 0, "tier": "verified", "related_ids": []} |
| OV-6.1 | SIMILARITY_DUPLICATE_THRESHOLD == 0.85 | PASS | SIMILARITY_DUPLICATE_THRESHOLD=0.85 |
| OV-6.2 | SIMILARITY_THRESHOLD == 0.55 | PASS | SIMILARITY_THRESHOLD=0.55 |
| OV-7.1 | STALE_DECAY_MULTIPLIERS 包含必需 key | PASS | keys=['architecture', 'config', 'debug', 'default', 'product', 'strategy', 'user_preference', 'workflow'] |
| OV-7.2 | user_preference multiplier == 3.0 | PASS | user_preference=3.0, expected=3.0 |
| OV-7.3 | debug multiplier == 0.5 | PASS | debug=0.5, expected=0.5 |
| OV-7.4 | default multiplier == 1.0 | PASS | default=1.0, expected=1.0 |
| OV-8 | doctor MCP JSON/Markdown 输出结构 | FAIL | doctor MCP failed: Error executing tool doctor: 'Engram' object has no attribute 'knowledge_overview' |
| OV-9 | update_identity MCP source_tool 溯源 | PASS | schema_has_source_tool=True; profile_after_update={'role': 'verify_tester', '_last_updated_by': 'codex_verify', 'role_provenance': {'by': 'codex_verify', 'at': '2026-05-27T02:28:23'}} |
| OV-10 | docs/cross-tool-guide.md 存在且含关键内容 | PASS | path=E:\Personal Intelligence Identity Asset\engram\docs\cross-tool-guide.md; checks={'跨工具': True, '跨会话': True, 'doctor': True} |

## 总结

通过: 16/18
失败: 2

## 备注

- `pyproject.toml` 当前版本号是 `3.29.3`，任务标题为 `v3.29.4`，版本号本身未列入 18 项判定。
- OV-8/OV-9 通过 MCP stdio transport 调用，并设置 `ENGRAM_TOOLS=all` 暴露完整工具集。
- OV-9 会临时写入真实 profile；脚本在验证后恢复了原始 `profile.json` 文件内容。
