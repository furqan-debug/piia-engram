# Engram v3.29.4 记忆系统优化调整报告

日期: 2026-05-27
基于: 全审计 158/159 (99.4%) 结果 + Codex 8 项优化分析
执行者: Claude Code

---

## 一、已完成的代码修改

### P0-1: 修复读操作写副作用（3 处）

**问题**: `export_identity_card()`、`export_cursor_rules()`、`import_from_cursor_rules()` 中的 `get_lessons()` / `get_decisions()` 调用未传 `_update_access=False`，导致纯读操作更新了 `last_reviewed` 和 `access_count`，污染生命周期统计。

**修改文件**:
| 文件 | 行号 | 修改 |
|------|------|------|
| `reports_identity.py` | 104 | `get_lessons(limit=30)` → `get_lessons(limit=30, _update_access=False)` |
| `compat.py` | 175 | `get_lessons(limit=50)` → `get_lessons(limit=50, _update_access=False)` |
| `compat.py` | 184 | `get_decisions(limit=30)` → `get_decisions(limit=30, _update_access=False)` |
| `compat.py` | 289 | `get_lessons(limit=MAX_KNOWLEDGE_ENTRIES)` → 添加 `_update_access=False` |

**影响**: 消除了 4 个只读场景的写副作用。MCP 工具层的 `get_lessons` 保留默认行为（用户主动查阅应计入访问次数）。

### P0-2: Identity 层 description 追加保护 + 字段级溯源

**问题**: `update_profile()` 使用 `dict.update()` 覆写所有字段。多工具场景下（CC 写 description → Codex 再写），先写的内容被后写覆盖。

**修改文件**: `core.py` `update_profile()`

**新行为**:
1. **description 追加合并**: 新 token 追加到现有 description 末尾，已存在的 token 跳过
2. **字段级溯源** (`_provenance`): 每个被修改的字段记录 `{by: tool_name, at: timestamp}`
3. **`_last_updated_by`**: 记录最后一次修改来自哪个工具
4. **MCP 入口 `update_identity`**: 新增 `source_tool` 参数，传入 profile 层

**自检结果**:
- Tool A 写 `marker_A` → Tool B 写 `marker_B` → description = `"marker_A marker_B"` ✅
- Tool A 再写 `marker_A` → description 不变（去重） ✅
- `_provenance` 正确记录每次修改来源 ✅

### P1-1: 三级去重分类

**问题**: `add_lesson` 和 `add_decision` 的去重是二元判断（≥55% 即拒绝），相似但不同的知识被错误丢弃。

**修改文件**: `core.py` `add_lesson()`, `add_decision()`; `storage.py` 新增常量

**新行为**:
| 相似度 | 处理 | 状态 |
|--------|------|------|
| ≥ 85% | 拒绝 | `status: "duplicate"` |
| 55%-84% | 添加 + 自动链接 | `related_ids` 双向绑定 + `_dedup_note` |
| < 55% | 正常添加 | 无特殊处理 |

**新增常量**: `SIMILARITY_DUPLICATE_THRESHOLD = 0.85`

**自检结果**:
- "Python虚拟环境管理最佳实践" + "Python虚拟环境管理最佳实践（补充说明）" → related (83%) ✅
- 完全相同内容 → duplicate ✅

### P1-2: 类型感知过期衰减

**问题**: 所有知识使用统一的 30 天过期标准，用户偏好和调试技巧用同一把尺子衡量不合理。

**修改文件**: `storage.py` 新增 `STALE_DECAY_MULTIPLIERS`; `reports_analytics.py` `knowledge_overview()` 中使用

**衰减策略**:
| 领域 | 复审周期 | 归档周期 |
|------|----------|----------|
| user_preference | 90 天 | 180 天 |
| architecture / strategy | 60 天 | 120 天 |
| product | 45 天 | 90 天 |
| workflow（默认） | 30 天 | 60 天 |
| debug / config | 15 天 | 30 天 |

### P2-1: Doctor 自诊断 MCP 工具

**新增文件**: `mcp_server.py` 中添加 `doctor()` 工具

**检查项目** (8 项):
1. identity_completeness — profile 字段完整性
2. identity_provenance — 溯源数据存在性
3. knowledge_volume — 知识条目数量
4. stale_knowledge — 过期知识数量
5. near_duplicates — 近似重复对数
6. decision_conflicts — 冲突决策检测
7. health_score — 综合健康评分
8. quick_context_freshness — 快照文件新鲜度

支持 `markdown` 和 `json` 两种输出格式。

### P2-2: 跨工具/跨会话用户指南

**新增文件**: `docs/cross-tool-guide.md`

覆盖内容：核心概念、配置方法、跨会话恢复（三层通路）、多工具共存机制、Doctor 使用、FAQ。

---

## 二、自检汇总

| 检查项 | 结果 |
|--------|------|
| 模块导入 (storage) | PASS |
| 模块导入 (core) | PASS |
| 模块导入 (reports_analytics) | PASS |
| 模块导入 (reports_identity) | PASS |
| 模块导入 (compat) | PASS |
| 模块导入 (mcp_server) | PASS |
| Description 追加合并 | PASS |
| 重复 marker 去重 | PASS |
| 三级 lesson 去重 | PASS |
| Decision 去重 | PASS |

---

## 三、未实施项（Codex 建议中降级或推迟的）

| 建议 | 状态 | 原因 |
|------|------|------|
| Core API / MCP API 契约测试 | 推迟到 P3 | 需要完整测试框架搭建 |
| 跨 AI ownership/visibility 字段 | 部分实施 | `_provenance` + `source_tool` 已覆盖核心需求，`owned_by`/`can_modify_by` 等细粒度权限暂不需要 |
| P4.12 project snapshot 路径规范化 | 已知问题 | 需排查 `_project_id()` 在不同调用路径下的行为差异 |

---

## 四、修改文件清单

| 文件 | 修改类型 |
|------|----------|
| `src/piia_engram/storage.py` | 新增 `SIMILARITY_DUPLICATE_THRESHOLD`, `STALE_DECAY_MULTIPLIERS` |
| `src/piia_engram/core.py` | 三级去重逻辑、`update_profile()` 追加+溯源 |
| `src/piia_engram/reports_identity.py` | 修复读副作用 |
| `src/piia_engram/reports_analytics.py` | 类型感知过期衰减 |
| `src/piia_engram/compat.py` | 修复读副作用（3处） |
| `src/piia_engram/mcp_server.py` | `doctor()` 工具 + `update_identity` 增加 `source_tool` |
| `docs/cross-tool-guide.md` | 新增用户指南 |
