# Codex Engram 记忆单元审计 — 有效性报告

日期: 2026-05-27
Engram 版本: 3.29.3
验证方式: unit_write.py(阶段1) -> unit_verify.py(阶段3, 新进程)

## 一、各功能有效性

| 子系统 | 通过 | 有效性 |
|--------|------|--------|
| S1 身份层 | 6/6 | 有效 |
| S2 知识层 | 10/10 | 有效 |
| S3 检索层 | 6/6 | 有效 |
| S4 上下文会话 | 6/6 | 有效 |
| S5 生命周期 | 6/6 | 有效 |
| S6 工具图谱 | 3/3 | 有效 |
| V-Chain 集成链 | 9/9 | 有效 |

## 二、逐项结果

| Case | 结果 | 备注 |
|------|------|------|
| V1.1 profile role | PASS | role=codex_tester |
| V1.2 profile description | PASS | description=codex_unit_test_marker_20260527 cc_self_test_marker_20260527 cross_ai_test_marker |
| V1.3 preferences communication | PASS | communication=sync |
| V1.4 trust restricted_fields | PASS | restricted=['email', 'phone'] |
| V1.5 quality rules | PASS | rules=['codex_unit_test_rule'] |
| V1.6 safe profile | PASS | safe_keys=['description', 'language', 'role', 'tech_stack', 'technical_level', 'updated_at'] |
| V2.1 lessons count | PASS | count=5 |
| V2.2 search pytest | PASS | hits=5 |
| V2.3 search asyncio | PASS | hits=20 |
| V2.4 search file lock | PASS | hits=20 |
| V2.5 decision pytest | PASS | decisions=107 |
| V2.6 decision GitHub Actions | PASS | decisions=107 |
| V2.7 playbook exists | PASS | playbooks=1 |
| V2.8 playbook steps | PASS | id=384e391abe23; steps=3 |
| V2.9 memory_store route | PASS | query=memory_store 路由 |
| V2.10 lesson source_tool | PASS | lessons=5 bad=[] |
| V3.1 search all count | PASS | hits=65 |
| V3.2 scope lessons | PASS | lessons=30 |
| V3.3 filter domain | PASS | hits=9 |
| V3.4 find similar | PASS | total=5 |
| V3.5 suggest merges | PASS | suggestions=30 |
| V3.6 relevant knowledge | PASS | items=8 |
| V4.1 recent context | PASS | sessions=5 |
| V4.2 list sessions | PASS | sessions=5 |
| V4.3 context quick | PASS | len=323 |
| V4.4 context standard | PASS | len=2298 |
| V4.5 context full longer | PASS | standard=2298 full=2790 |
| V4.6 quick_context file | PASS | path=C:\Users\pp3x3\.engram\quick_context.md; len=2205 |
| V5.1 wrapup knowledge | PASS | lessons=200 decisions=107 |
| V5.2 overview | PASS | health_score=95 total_lessons=200 |
| V5.3 project context | PASS | keys=['created_at', 'known_issues', 'last_codex_audit', 'notes', 'project_folder', 'tech_stack', 'title', 'updated_at'] |
| V5.4 identity card | PASS | len=1800 |
| V5.5 stale knowledge | PASS | stale_lessons=1 |
| V5.6 health score range | PASS | health_score=95 |
| V6.1 find tool | PASS | hits=1 |
| V6.2 list tools | PASS | tools=5 |
| V6.3 tool version | PASS | version=2.0 |
| VC1.1 context quick | PASS | len=323 |
| VC2.1 search access_count | PASS | max_access_count=8 |
| VC5.1 wrapup searchable | PASS | lessons=200 decisions=107 |
| VC6.1 execution status | PASS | completed=2/3 |
| VC7.1 conflicting choices | PASS | choices_present=(True, True) |
| VC8.1 merge suggestions | PASS | suggestions=30 |
| VC9.1 stale lesson | PASS | stale_lessons=1 |
| VC10.1 identity card aggregate | PASS | checks=[True, True, True, True]; len=1800 |
| VC-persist cross process | PASS | required_files=['E:\\Personal Intelligence Identity Asset\\engram\\experiments\\memory_audit\\codex_unit_seed.json', 'E:\\Personal Intelligence Identity Asset\\engram\\experiments\\memory_audit\\results\\unit_write_log.txt', 'E:\\Personal I |

## 三、跨执行持久化评估

- Seed 文件: `E:\Personal Intelligence Identity Asset\engram\experiments\memory_audit\codex_unit_seed.json`
- 总验证: 46/46
- 失败: 0

## 四、总评 + 发现的问题 + 建议

阶段 1 写入的数据在阶段 3 新进程中可完整读取，记忆持久化链路有效。
