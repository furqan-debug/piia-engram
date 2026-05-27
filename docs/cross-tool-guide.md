# Engram 跨工具 & 跨会话使用指南

> 版本: 3.29.4+ | 更新日期: 2026-05-27

本指南面向同时使用多个 AI 工具（Claude Code、Codex、Cursor 等）的用户，说明如何让 Engram 在不同工具和对话之间保持记忆连贯。

---

## 目录

1. [核心概念](#1-核心概念)
2. [配置](#2-配置)
3. [跨会话记忆恢复](#3-跨会话记忆恢复)
4. [多工具共存](#4-多工具共存)
5. [Doctor 自诊断](#5-doctor-自诊断)
6. [常见问题](#6-常见问题)

---

## 1. 核心概念

### 记忆是本地资产

Engram 将所有数据存储在本机 `~/.engram/` 目录下。任何连接了 Engram MCP 的 AI 工具都能读写同一份数据。这意味着：

- Claude Code 写入的经验教训，Codex 可以立即读到
- Cursor 做的决策记录，Claude Code 在下一次会话中能看到
- 不依赖任何云端同步——你的记忆完全属于你

### 数据分层

| 层 | 说明 | 跨工具可见 | 跨会话持久 |
|----|------|-----------|-----------|
| **Identity** | 你的角色、偏好、技术栈 | 是 | 是 |
| **Knowledge** | 经验教训、决策、操作手册 | 是 | 是 |
| **Context** | 会话上下文、近期操作 | 是 | 是 |
| **Tool Registry** | 本地安装的工具信息 | 是 | 是 |

### source_tool 溯源

每条知识记录都有 `source_tool` 字段，标记是哪个工具写入的。用于：
- 追溯知识来源（"这条教训是 Codex 还是 Claude Code 写的？"）
- 过滤查看（"只看 Claude Code 的经验"）
- 冲突时判断权威来源

---

## 2. 配置

### 2.1 基础安装

每个 AI 工具都需要配置 Engram 作为 MCP Server：

**Claude Code** — 在 `~/.claude/` 或项目的 `.mcp.json` 中：
```json
{
  "mcpServers": {
    "engram": {
      "command": "piia-engram-mcp",
      "args": ["--transport", "stdio"]
    }
  }
}
```

**Codex** — 在 codex 配置中添加 MCP server 指向同一命令。

**Cursor** — 在 Cursor MCP 设置中添加相同配置。

### 2.2 共享指令文件

所有工具共享的行为规则放在：
```
~/.engram/shared_instructions.md
```

各工具的私有指令放在各自的配置中（如 `~/.claude/CLAUDE.md`）。共享指令确保所有工具对 Engram 的使用方式一致。

### 2.3 Quick Context 快照

Engram 自动维护一份 `~/.engram/quick_context.md` 文件——你的身份卡片快照。AI 工具启动时可以直接读取此文件，无需调用 MCP，实现毫秒级冷启动。

---

## 3. 跨会话记忆恢复

### 3.1 自动恢复机制

当你在新对话中开始工作，Engram 提供三个层级的上下文恢复：

| 层级 | 方式 | 内容 | 速度 |
|------|------|------|------|
| **Quick** | 读取 `quick_context.md` | 身份 + 偏好 + 近期经验 | 毫秒级 |
| **Standard** | `get_user_context(level="standard")` | Quick + 决策 + 项目上下文 | <1秒 |
| **Full** | `get_user_context(level="full")` | Standard + 冲突检测 + 同步状态 | 1-2秒 |

**推荐做法**：
- 大多数对话：直接读 `quick_context.md`（通路 1）
- 需要深度上下文：调用 `get_user_context(level="standard")`（通路 2）
- 全量回顾：仅在明确需要时用 `full` 级别

### 3.2 会话保存

每次重要对话结束时，AI 工具应调用：
```
save_agent_context(tool="claude_code", content="会话摘要...", project_folder="...")
```

这会将当前会话的关键上下文保存为持久记录，下次恢复时可用。

### 3.3 Wrap-up 自动提取

调用 `wrap_up_session` 时，Engram 会自动：
1. 从会话内容中提取经验教训（标记为 `tier: "staging"`）
2. 提取关键决策
3. 保存会话上下文
4. 更新 `quick_context.md`

Staging 层的知识在被访问 3 次后自动晋升为 `verified`。

---

## 4. 多工具共存

### 4.1 Description 字段保护（v3.29.4+）

当多个工具写入 profile 的 description 字段时，Engram 使用 **追加合并** 语义：

- Tool A 写入 `"标记A"` → description = `"标记A"`
- Tool B 写入 `"标记B"` → description = `"标记A 标记B"`（追加，不覆盖）
- Tool A 再写 `"标记A"` → description 不变（已存在，跳过）

这确保多个工具的标记/信息共存，不会互相覆盖。

### 4.2 字段级溯源（v3.29.4+）

Profile 现在记录每个字段的最后修改来源：

```json
{
  "role": "开发者",
  "_provenance": {
    "role": {"by": "claude_code", "at": "2026-05-27T01:00:00"},
    "language": {"by": "codex", "at": "2026-05-27T02:00:00"}
  },
  "_last_updated_by": "codex"
}
```

调用 `update_identity` 时传入 `source_tool` 参数即可启用：
```
update_identity(field="profile", updates_json='{"role":"开发者"}', source_tool="claude_code")
```

### 4.3 知识去重（v3.29.4+）

当不同工具写入相似知识时，Engram 使用三级去重：

| 相似度 | 处理 | 说明 |
|--------|------|------|
| ≥ 85% | **拒绝** | 精确重复，不添加 |
| 55%-84% | **关联** | 添加但自动链接 `related_ids` |
| < 55% | **通过** | 正常添加 |

这意味着：
- Claude Code 和 Codex 写入完全相同的教训 → 只保留一条
- 写入相似但有差异的教训 → 两条都保留，并自动标记关联
- 写入不相关的教训 → 各自独立存储

### 4.4 source_tool 过滤

查看特定工具的知识：
```
get_lessons(source_tool="claude_code")
get_decisions(source_tool="codex")
```

搜索时也支持按来源过滤：
```
search_knowledge(query="部署", scope="lessons")
```

### 4.5 冲突决策管理

当不同工具或不同时间做出矛盾决策时（如 "部署用 Docker" vs "部署用裸机"），Engram 会检测到冲突并在 `get_user_context(level="full")` 中报告。

你可以用 `search_knowledge` 查找冲突对，然后决定保留哪个、归档哪个。

---

## 5. Doctor 自诊断

v3.29.4+ 新增 `doctor` MCP 工具，可随时检查记忆系统健康状态。

### 调用方式

在任何连接了 Engram 的 AI 工具中说：
> "帮我跑一下 Engram 的 doctor 检查"

AI 工具会调用 `doctor()` 并返回类似下面的报告：

| 检查项 | 状态 | 详情 |
|--------|------|------|
| identity_completeness | PASS | profile 完整 |
| identity_provenance | PASS | 字段级溯源已启用 |
| knowledge_volume | PASS | lessons=42, decisions=15 |
| stale_knowledge | WARN | 需复审: 12, 可归档: 3 |
| near_duplicates | PASS | 近似重复对数: 2 |
| decision_conflicts | PASS | 无冲突 |
| health_score | PASS | 87/100 |
| quick_context_freshness | PASS | 最后更新: 2.3 小时前 |

### 支持 JSON 输出

```
doctor(output_format="json")
```

返回结构化 JSON，便于自动化处理。

---

## 6. 常见问题

### Q: 两个工具同时写入会冲突吗？

Engram 使用文件级锁（portalocker）防止并发写入损坏。同一时刻只有一个进程能写入同一个文件。但两个工具的写入是串行的，不会丢数据。

### Q: 我切换了 AI 工具，之前的记忆还在吗？

是的。所有数据存储在 `~/.engram/` 下，任何连接了 Engram MCP 的工具都能访问。即使你从 Claude Code 切到 Codex，再切到 Cursor，记忆完全相同。

### Q: 怎么知道某条知识是哪个工具写的？

每条知识都有 `source_tool` 字段。可以用 `get_lessons(source_tool="claude_code")` 过滤查看。Identity Card（`get_identity_card()`）中也会标注来源。

### Q: Quick Context 会自动更新吗？

会。每次调用 `wrap_up_session` 或 `get_user_context` 时，`quick_context.md` 都会自动刷新。

### Q: 如何清理过期知识？

1. 调用 `doctor()` 查看哪些知识过期
2. 调用 `knowledge_overview()` 获取详细生命周期报告
3. 对过期条目调用 `archive_lesson(id)` 归档
4. 或者使用 Review UI：`request_outline_review()` 生成可视化审阅界面

### Q: 跨会话的上下文会无限增长吗？

不会。Engram 有以下机制控制增长：
- 每类知识最多 200 条（`MAX_KNOWLEDGE_ENTRIES`）
- 超限时自动淘汰 staging 层 → 再淘汰最旧 verified 层
- 过期知识按类型差异化衰减（用户偏好 90 天，调试技巧 15 天）
- `wrap_up_session` 提取的知识默认为 staging，只有被多次访问才晋升

### Q: 多工具同时操作 identity 会覆盖吗？

v3.29.4+ 中，description 字段使用追加语义，不会覆盖。其他字段（role, language 等）仍然是后写覆盖，但有 `_provenance` 溯源记录，可以追查是谁改的。

---

## 附录: 类型感知过期策略

不同类型的知识有不同的过期周期（v3.29.4+）：

| 知识领域 | 复审周期 | 归档周期 | 说明 |
|----------|----------|----------|------|
| user_preference | 90 天 | 180 天 | 用户偏好变化慢 |
| architecture | 60 天 | 120 天 | 架构决策较稳定 |
| strategy | 60 天 | 120 天 | 战略方向 |
| product | 45 天 | 90 天 | 产品决策 |
| workflow | 30 天 | 60 天 | 工作流程（默认） |
| debug | 15 天 | 30 天 | 调试技巧衰减快 |
| config | 15 天 | 30 天 | 配置问题衰减快 |

领域通过 `domain` 字段匹配。未匹配的默认使用 30/60 天周期。
