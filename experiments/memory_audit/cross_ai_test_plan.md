# 跨 AI 记忆有效性验证方案

## 核心目标

Engram 的核心价值：**一次记忆，所有 AI 工具共享**。
本方案验证 Claude Code 和 Codex 之间的记忆互通性。

## 测试架构

```
Phase 1: Claude Code 写入（自测执行）
    ↓
Phase 2: Codex 盲读验证（Codex 任务包）
    ↓
Phase 3: Codex 写入（Codex 任务包）
    ↓
Phase 4: Claude Code 盲读验证（自测执行）
```

**关键**：Phase 2 的 Codex 不知道 Phase 1 写了什么具体值，
只知道"Claude Code 应该已经写了一些东西"，用搜索和读取验证是否存在。

---

## Phase 1：Claude Code 写入（Claude Code 执行）

在**真实的 Engram 数据目录**（`~/.engram/`）中写入测试数据，打上标记便于识别。

### 写入清单（10 项）

| # | 操作 | 数据 | source_tool |
|---|------|------|-------------|
| W1 | add_lesson | summary="跨AI测试：Claude Code写入的pytest经验", domain="cross_ai_test" | claude_code |
| W2 | add_decision | question="跨AI测试：部署方案选择", choice="Docker Compose", reasoning="本地开发一致性" | claude_code |
| W3 | add_playbook | name="跨AI测试：发布流程", triggers=["cross_ai_release"], 3步 | claude_code |
| W4 | update_identity(profile) | 添加自定义字段如 description 含 "cross_ai_test_marker" | claude_code |
| W5 | save_agent_context | tool="claude_code", content="Cross-AI test session by Claude Code at {timestamp}" | claude_code |
| W6 | register_tool | name="cross_ai_test_tool", path="/test/path", category="cli" | claude_code |
| W7 | add_lesson | summary="跨AI测试：中文CJK搜索验证-文件锁机制", domain="cross_ai_test" | claude_code |
| W8 | add_decision | question="跨AI测试：存储格式", choice="JSON", reasoning="本地优先无依赖" | claude_code |
| W9 | memory_store | kind="lesson", summary="跨AI测试：memory_store路由验证", domain="cross_ai_test" | claude_code |
| W10 | save_project_snapshot | project_folder 含 "cross_ai_test" 标记 | claude_code |

**写入后记录**：将所有写入的 ID、timestamp 保存到
`experiments/memory_audit/cross_ai_seed.json`，供 Phase 4 用。

---

## Phase 2：Codex 盲读验证（Codex 任务包）

Codex 的任务：**不看 seed.json**，通过搜索和读取验证 Claude Code 的写入是否可见。

### 验证清单（15 项）

```
R1   search_knowledge(query="跨AI测试") → 应至少返回 3 条结果
R2   search_knowledge(query="pytest", filters={"domain":"cross_ai_test"}) → 命中 W1
R3   get_lessons(domain="cross_ai_test") → 至少 2 条，且 source_tool 含 "claude_code"
R4   get_decisions() → 含 question 包含"部署方案"的 decision
R5   search_knowledge(query="文件锁") → 命中 W7（CJK 搜索跨 AI 验证）
R6   get_playbooks() → 含 name 包含"跨AI测试"的 playbook
R7   get_playbook(id) → steps 长度 = 3（根据 R6 返回的 id）
R8   get_profile() → description 含 "cross_ai_test_marker"
R9   get_recent_context(tool="claude_code") → 内容含 "Cross-AI test session"
R10  find_tool(query="cross_ai_test_tool") → 命中
R11  get_relevant_knowledge(project_folder=engram仓库路径) → 有结果返回
R12  search_knowledge(query="memory_store路由") → 命中 W9
R13  get_project_context(project_folder含cross_ai_test) → snapshot 存在
R14  get_user_context(level="standard") → 输出含 "cross_ai_test" 相关内容
R15  list_agent_sessions(tool="claude_code") → 至少 1 条记录
```

---

## Phase 3：Codex 写入（Codex 任务包）

Codex 写入自己的测试数据，供 Phase 4 的 Claude Code 验证。

### 写入清单（8 项）

| # | 操作 | 数据 | source_tool |
|---|------|------|-------------|
| CW1 | add_lesson | summary="跨AI测试：Codex写入的CI/CD经验", domain="cross_ai_test_codex" | codex |
| CW2 | add_decision | question="跨AI测试Codex：缓存策略", choice="Redis", reasoning="高性能" | codex |
| CW3 | add_playbook | name="跨AI测试Codex：部署流程", triggers=["cross_ai_deploy_codex"], 2步 | codex |
| CW4 | save_agent_context | tool="codex", content="Cross-AI test session by Codex at {timestamp}" | codex |
| CW5 | register_tool | name="codex_test_tool", path="/codex/path", category="runtime" | codex |
| CW6 | add_lesson | summary="跨AI测试Codex：TypeScript类型安全最佳实践", domain="cross_ai_test_codex" | codex |
| CW7 | memory_store | kind="decision", question="跨AI测试Codex：日志方案", choice="structured logging" | codex |
| CW8 | save_project_snapshot | project_folder 含 "cross_ai_test_codex" | codex |

写入后保存 ID 到 `experiments/memory_audit/cross_ai_codex_seed.json`。

---

## Phase 4：Claude Code 盲读验证（Claude Code 执行）

Claude Code 验证 Codex 写入的数据可见。

### 验证清单（12 项）

```
CR1  search_knowledge(query="Codex写入") → 至少 1 条
CR2  get_lessons(domain="cross_ai_test_codex") → 至少 2 条，source_tool="codex"
CR3  get_decisions() → 含 question 包含"缓存策略"
CR4  search_knowledge(query="TypeScript类型安全") → 命中 CW6
CR5  get_playbooks() → 含 name 包含"Codex"的 playbook
CR6  get_recent_context(tool="codex") → 含 "Cross-AI test session by Codex"
CR7  find_tool(query="codex_test_tool") → 命中
CR8  search_knowledge(query="structured logging") → 命中 CW7
CR9  get_user_context(level="standard") → 含 cross_ai_test_codex 相关内容
CR10 list_agent_sessions(tool="codex") → 至少 1 条
CR11 get_project_context(含cross_ai_test_codex) → snapshot 存在
CR12 search_knowledge(query="跨AI测试", scope="all") → 同时含 claude_code 和 codex 来源
```

---

## 跨 AI 独有验证维度（Phase 2 和 Phase 4 共有）

### source_tool 来源追溯

验证同一个知识库中不同来源的数据能被正确区分：

```
X1  get_lessons() 全量 → 过滤 source_tool="claude_code" 的条目数
X2  get_lessons() 全量 → 过滤 source_tool="codex" 的条目数
X3  X1 和 X2 的条目互不重叠（ID 不同）
X4  search_knowledge(query="跨AI测试") → 结果中同时存在两个来源
```

### 时序一致性

```
X5  Claude Code 写的数据 created_at 早于 Codex 写的
X6  两者的数据在 get_user_context 中按时间排序正确
```

---

## 清理方案

测试完成后清理标记数据（**不要自动清理，先人工确认**）：

- 搜索 domain 含 "cross_ai_test" 的所有条目
- 搜索 summary 含 "跨AI测试" 的所有条目
- 列出 → 确认 → 手动删除或标记 outdated

---

## 通过门槛

| Phase | 验证项 | 通过标准 |
|-------|--------|---------|
| Phase 2 Codex盲读 | 15 项 | 15/15 |
| Phase 4 Claude盲读 | 12 项 | 12/12 |
| 跨AI独有验证 | 6 项 | 6/6 |
| **合计** | **33** | **33/33** |

全部通过 = Engram 跨 AI 记忆功能 **有效**。
