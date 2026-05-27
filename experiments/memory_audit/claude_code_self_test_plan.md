# Claude Code 自测方案：Engram 记忆功能全面审计

## 核心原则

1. **跨聊天框验证**：写入和验证必须在**不同的对话**中完成，证明记忆跨会话持久化
2. **真实数据目录**：使用 `~/.engram/` 真实目录，不用临时目录（跨会话必须持久化）
3. **不动主代码**，纯黑盒验证
4. 测试数据统一打标 `domain="cc_self_test"`，方便清理
5. 结束后输出**有效性报告**

## 测试架构

```
┌──────────────────────────────────────────────────────────┐
│                   Claude Code 自测                        │
│                                                          │
│  Session A（对话1）          Session B（对话2）            │
│  ┌──────────────────┐       ┌──────────────────┐        │
│  │ Phase W: 写入     │  ──→  │ Phase V: 验证     │        │
│  │ 6 子系统全量写入   │       │ 6 子系统全量读取   │        │
│  │ 10 集成链写入端   │       │ 10 集成链验证端   │        │
│  │ 输出 seed.json    │       │ 输出有效性报告    │        │
│  └──────────────────┘       └──────────────────┘        │
└──────────────────────────────────────────────────────────┘
```

**关键**：Session A 结束后，必须开一个**新对话** Session B 来验证。
Session B 只读取 Engram 数据 + seed.json 中的预期值，**不读 Session A 的对话历史**。

---

## Phase W：写入（Session A 执行）

### 使用 MCP 工具直接调用

Claude Code 自测不写 Python 脚本，直接通过 MCP 工具调用 Engram。

### W-S1：身份层写入（4 项）

```
W-S1.1  update_identity(field='profile', updates_json='{"role":"cc_test_architect","language":"zh","description":"cc_self_test_marker_20260527"}')
W-S1.2  update_identity(field='preferences', updates_json='{"communication":"async","tool_preferences":{"claude_code":"primary"}}')
W-S1.3  update_identity(field='trust_boundaries', updates_json='{"restricted_fields":["email","phone"],"default_sharing":"local_only"}')
W-S1.4  update_identity(field='quality_standards', updates_json='{"acceptance_threshold":4,"rules":["cc_self_test_rule"]}')
```

### W-S2：知识层写入（8 项）

```
W-S2.1  add_lesson(summary="CC自测：pytest fixture 用 tmp_path 隔离测试环境", domain="cc_self_test", source_tool="claude_code")
W-S2.2  add_lesson(summary="CC自测：urllib 默认不发 User-Agent 导致 Cloudflare 403", domain="cc_self_test", source_tool="claude_code")
W-S2.3  add_lesson(summary="CC自测：portalocker 实现跨进程文件锁", domain="cc_self_test", source_tool="claude_code")
W-S2.4  add_decision(question="CC自测：数据库选型", choice="SQLite", reasoning="本地优先无服务端依赖", domain="cc_self_test", source_tool="claude_code")
W-S2.5  add_decision(question="CC自测：部署方式", choice="Docker Compose", reasoning="开发环境一致性", domain="cc_self_test", source_tool="claude_code")
W-S2.6  add_playbook(name="CC自测：PyPI发布流程", triggers=["cc_test_release","cc_test_publish"], steps=[{"order":1,"action":"build","detail":"python -m build"},{"order":2,"action":"test","detail":"pytest -x"},{"order":3,"action":"upload","detail":"twine upload dist/*"}], domain="cc_self_test", source_tool="claude_code")
W-S2.7  memory_store(kind="lesson", summary="CC自测：memory_store统一路由验证", domain="cc_self_test", source_tool="claude_code")
W-S2.8  add_lesson(summary="CC自测：CJK中文搜索-文件锁机制详解", domain="cc_self_test", source_tool="claude_code")
```

### W-S4：上下文会话写入（2 项）

```
W-S4.1  save_agent_context(tool="claude_code", content="CC自测跨会话验证：Session A 写入于 {timestamp}。这条内容应在 Session B 中可见。", project_folder="E:/Personal Intelligence Identity Asset/engram")
W-S4.2  refresh_quick_context()
```

### W-S5：生命周期写入（1 项）

```
W-S5.1  wrap_up_session(summary="CC自测会话：完成了UA修复，踩坑发现urllib不发Header。决定所有HTTP请求都加UA。流程是先build再test再publish。", project_folder="E:/Personal Intelligence Identity Asset/engram", source_tool="claude_code")
```

### W-S6：工具图谱写入（1 项）

```
W-S6.1  register_tool(name="cc_self_test_tool", path="/test/cc/path", category="cli", version="1.0", purpose="Claude Code自测工具", source_tool="claude_code")
```

### W-Chain：集成链写入端（额外 3 项）

```
W-C6.1  记录 W-S2.6 的 playbook_id → prepare_playbook_execution → update_execution_step(step1=completed, step2=completed)
W-C7.1  add_decision(question="CC自测：部署方案选择", choice="裸机部署", reasoning="降低成本", domain="cc_self_test") → 应与 W-S2.5 冲突
W-C9.1  （可选）手动设置某条 lesson 的 last_reviewed 为 60 天前（写 JSON 文件）
```

### 写入后：保存 seed

将所有写入的 ID、预期值保存到 `experiments/memory_audit/cc_self_test_seed.json`：

```json
{
  "written_at": "2026-05-27T...",
  "session": "A",
  "identity": {
    "profile_marker": "cc_self_test_marker_20260527",
    "role": "cc_test_architect"
  },
  "lessons": [
    {"id": "...", "summary_keyword": "pytest fixture", "domain": "cc_self_test"},
    {"id": "...", "summary_keyword": "urllib User-Agent", "domain": "cc_self_test"},
    ...
  ],
  "decisions": [...],
  "playbooks": [...],
  "tools": [...],
  "session_context": {"tool": "claude_code", "keyword": "CC自测跨会话验证"}
}
```

---

## Phase V：验证（Session B 执行 — 新对话）

### Session B 的指令

```
打开新的 Claude Code 对话，给出指令：

"执行 Engram 记忆跨会话验证的 Phase V。
读取 experiments/memory_audit/cc_self_test_seed.json 中的预期值，
然后逐项验证所有写入是否在新会话中可见。
结果输出到 experiments/memory_audit/results/cc_self_test_report.md"
```

### V-S1：身份层验证（6 项）

```
V-S1.1  get_profile() → role = "cc_test_architect"
V-S1.2  get_profile() → description 含 "cc_self_test_marker_20260527"
V-S1.3  get_preferences() → communication = "async"
V-S1.4  get_trust_boundaries() → restricted_fields 含 "email"
V-S1.5  get_quality_standards() → rules 含 "cc_self_test_rule"
V-S1.6  get_profile(safe=True) → 不含 restricted_fields 中的字段值
```

### V-S2：知识层验证（10 项）

```
V-S2.1  get_lessons(domain="cc_self_test") → 数量 ≥ 4
V-S2.2  search_knowledge(query="pytest fixture") → 命中，source_tool="claude_code"
V-S2.3  search_knowledge(query="urllib User-Agent") → 命中
V-S2.4  search_knowledge(query="文件锁") → 命中（CJK 搜索验证）
V-S2.5  get_decisions() → 含 question 包含 "数据库选型" 且 choice="SQLite"
V-S2.6  get_decisions() → 含 "部署方式" 且 choice="Docker Compose"
V-S2.7  get_playbooks() → 含 name 包含 "PyPI发布" 的 playbook
V-S2.8  get_playbook(seed中的id) → steps 长度 = 3
V-S2.9  search_knowledge(query="memory_store统一路由") → 命中
V-S2.10 所有 lesson 的 source_tool = "claude_code"
```

### V-S3：检索层验证（6 项）

```
V-S3.1  search_knowledge(query="CC自测", scope="all") → 至少 5 条
V-S3.2  search_knowledge(query="CC自测", scope="lessons") → 只有 lesson 类型
V-S3.3  search_knowledge(query="CC自测", filters={"domain":"cc_self_test"}) → 全命中
V-S3.4  find_similar_knowledge(id=seed中某lesson_id) → 有相似结果
V-S3.5  suggest_merges() → 检查是否有 cc_self_test 域的合并建议
V-S3.6  get_relevant_knowledge(project_folder=engram仓库路径) → 有结果
```

### V-S4：上下文会话验证（6 项）

```
V-S4.1  get_recent_context(tool="claude_code") → 含 "CC自测跨会话验证"
V-S4.2  list_agent_sessions(tool="claude_code") → 至少 1 条
V-S4.3  get_user_context(level="quick") → 含 "cc_test_architect"
V-S4.4  get_user_context(level="standard") → 含 cc_self_test 相关知识
V-S4.5  get_user_context(level="full") → 长度 > standard
V-S4.6  读取 quick_context.md → 文件存在且含 profile 信息
```

### V-S5：生命周期验证（4 项）

```
V-S5.1  wrap_up 提取的知识 → get_lessons 中能找到从摘要提取的内容
V-S5.2  get_knowledge_overview() → 含 total_lessons, health_score
V-S5.3  get_project_context(project_folder=engram仓库路径) → snapshot 存在
V-S5.4  get_identity_card() → Markdown 含 "cc_test_architect" + 经验领域
```

### V-S6：工具图谱验证（3 项）

```
V-S6.1  find_tool(query="cc_self_test_tool") → 命中
V-S6.2  list_tools() → 含 cc_self_test_tool
V-S6.3  find_tool 返回的 version = "1.0"
```

### V-Chain：集成链验证（5 项）

```
V-C2.1  search_knowledge(query="pytest fixture") → 检查 access_count > 0（被搜索过）
V-C5.1  wrap_up 产生的 lesson/decision → 在知识库中可找到
V-C6.1  get_execution_status(playbook_id) → 完成 2/3 步
V-C7.1  get_decisions() 中同时存在 "Docker Compose" 和 "裸机部署" → 冲突对
V-C10.1 get_identity_card() → 同时含身份、偏好、知识、决策信息
```

---

## 有效性报告模板

Phase V 完成后，输出到 `experiments/memory_audit/results/cc_self_test_report.md`：

```markdown
# Claude Code Engram 记忆自测有效性报告

测试日期: YYYY-MM-DD
Engram 版本: X.Y.Z
跨会话验证: Session A (写入) → Session B (验证)

## 一、功能有效性评估

### 1. 身份层（Identity）
| 功能 | Case | 结果 | 有效性 |
|------|------|------|--------|
| Profile CRUD | V-S1.1, V-S1.2 | PASS/FAIL | 有效/无效 |
| Profile 安全过滤 | V-S1.6 | PASS/FAIL | 有效/无效 |
| Preferences | V-S1.3 | PASS/FAIL | 有效/无效 |
| Trust Boundaries | V-S1.4 | PASS/FAIL | 有效/无效 |
| Quality Standards | V-S1.5 | PASS/FAIL | 有效/无效 |
**子系统有效性**: X/6 PASS → 有效/部分有效/无效

### 2. 知识层（Knowledge）
| 功能 | Case | 结果 | 有效性 |
|------|------|------|--------|
| Lesson 写入+持久化 | V-S2.1~V-S2.4 | | |
| Decision 写入+持久化 | V-S2.5~V-S2.6 | | |
| Playbook 写入+持久化 | V-S2.7~V-S2.8 | | |
| memory_store 路由 | V-S2.9 | | |
| Source Tool 标记 | V-S2.10 | | |
**子系统有效性**: X/10 PASS

### 3. 检索层（Retrieval）
| 功能 | Case | 结果 | 有效性 |
|------|------|------|--------|
| 文本搜索 | V-S3.1~V-S3.2 | | |
| CJK 中文搜索 | V-S2.4 | | |
| Filter 过滤 | V-S3.3 | | |
| 相似度匹配 | V-S3.4 | | |
| 合并建议 | V-S3.5 | | |
| 项目相关推荐 | V-S3.6 | | |
**子系统有效性**: X/6 PASS

### 4. 上下文 & 会话层（Context & Session）
| 功能 | Case | 结果 | 有效性 |
|------|------|------|--------|
| Session 跨会话恢复 | V-S4.1 | | **关键** |
| Session 列表 | V-S4.2 | | |
| 三级上下文加载 | V-S4.3~V-S4.5 | | |
| Quick Context 快照 | V-S4.6 | | |
**子系统有效性**: X/6 PASS

### 5. 生命周期管理（Lifecycle）
| 功能 | Case | 结果 | 有效性 |
|------|------|------|--------|
| 自动提取（wrap_up） | V-S5.1 | | |
| 健康报告 | V-S5.2 | | |
| 项目快照 | V-S5.3 | | |
| Identity Card | V-S5.4 | | |
**子系统有效性**: X/4 PASS

### 6. 工具图谱（Tool Registry）
| 功能 | Case | 结果 | 有效性 |
|------|------|------|--------|
| 注册+查找 | V-S6.1~V-S6.2 | | |
| 版本追溯 | V-S6.3 | | |
**子系统有效性**: X/3 PASS

## 二、集成链有效性评估

| 链 | 描述 | 涉及子系统 | 结果 | 有效性 |
|----|------|-----------|------|--------|
| C2 | 写入→搜索→访问计数 | S2→S3→S5 | | |
| C5 | wrap_up 全链提取 | S4→S5→S2 | | |
| C6 | Playbook 执行追踪 | S2→执行 | | |
| C7 | 冲突检测联动 | S2→S2 | | |
| C10 | Identity Card 聚合 | S1+S2→输出 | | |
**集成链有效性**: X/5 PASS

## 三、跨会话持久化评估

| 验证点 | 结果 |
|--------|------|
| 身份数据跨会话保持 | |
| 知识数据跨会话保持 | |
| Session 上下文跨会话可恢复 | |
| 工具图谱跨会话保持 | |
| Quick Context 快照跨会话可用 | |
| 项目快照跨会话保持 | |
**跨会话持久化**: X/6 PASS

## 四、总结

| 维度 | 通过率 | 评价 |
|------|--------|------|
| 功能有效性 | X/35 | |
| 集成链有效性 | X/5 | |
| 跨会话持久化 | X/6 | |
| **总评** | **X/46** | **有效 / 部分有效 / 无效** |

### 发现的问题
1. ...

### 建议改进
1. ...
```

---

## 清理

验证完成后，搜索 `domain="cc_self_test"` 的所有条目，人工确认后清理。
**不要自动清理**，先输出报告让用户确认。
