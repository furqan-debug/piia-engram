# Engram 记忆功能全面审计 — 2026-05-27

## 测试矩阵

```
                    Claude Code 自测          Codex 测试
                    ─────────────           ──────────
单元审计(6子系统)    Phase W → Phase V       unit_write → unit_verify
集成链(10条)         含在 Phase W/V 中        test_chains (独立)
跨 AI 互通           Phase 1 + Phase 4       Phase 2 + Phase 3
                    ↑写入+盲读验证            ↑盲读验证+写入
```

## 方案文件

| 文件 | 位置 | 用途 |
|------|------|------|
| Claude Code 自测 | [`claude_code_self_test_plan.md`](claude_code_self_test_plan.md) | Claude Code 跨会话自测（Phase W → Phase V） |
| 跨 AI 验证 | [`cross_ai_test_plan.md`](cross_ai_test_plan.md) | 4 阶段接力：CC写→Codex读→Codex写→CC读 |
| Codex 单元审计 | `桌面/codex任务框架和规则/verification/codex-task-memory-audit-unit.md` | Codex 跨执行自测（write → verify） |
| Codex 集成链 | `桌面/codex任务框架和规则/verification/codex-task-memory-audit-chains.md` | 10 条环环相扣的集成链 |
| Codex 跨 AI | `桌面/codex任务框架和规则/verification/codex-task-memory-audit-cross-ai.md` | Codex 端的 Phase 2 + Phase 3 |

## 覆盖范围

- **6 大子系统**：身份、知识、检索、上下文会话、生命周期、工具图谱
- **60+ MCP 工具**：全部记忆相关工具覆盖
- **3 个验证维度**：功能有效性 + 集成链联动 + 跨会话/跨AI持久化
- **总 Case 数**：~150+（含两端重复验证）

## 执行顺序建议

1. **Codex 单元审计**（unit_write → unit_verify）— 验证基础功能
2. **Codex 集成链**（test_chains）— 验证子系统联动
3. **Claude Code 自测 Phase W**（写入）
4. **Codex 跨 AI Phase 2+3**（盲读+写入）
5. **Claude Code 自测 Phase V**（验证）+ **Phase 4**（盲读 Codex 数据）

## 产出

```
experiments/memory_audit/
├── scripts/               # 测试脚本
├── results/               # 测试结果和有效性报告
├── cc_self_test_seed.json # Claude Code 写入记录
├── codex_unit_seed.json   # Codex 写入记录
└── cross_ai_*_seed.json   # 跨 AI 写入记录
```
