# Release Playbook

发布 piia-engram 新版本的完整流程。每次 `git push` + `gh release create` 之前过一遍这份清单。

---

## 0. 触发时机

- **GitHub Release**：按维护者节奏发布。
- **PyPI publish**：跟随 GitHub Release（`publish.yml` workflow 自动触发）。
- **代码 commit + push**：可随时推，但单纯 commit 不算"发布"，只是节奏更细的检查点。

---

## 1. 发布前自检（必做）

### 1.1 测试 / 健康度

```bash
# Full pytest — 不允许任何失败
python -m pytest tests/ -q

# Doctor 自检（在干净环境跑）
engram doctor
```

最低门槛：
- 测试 100% 通过
- doctor 输出无 `[fail]`，`[warn]` 只允许出现在云目录检测等明确告知项

### 1.2 文档同步

- `pyproject.toml` 的 `version` 从 `X.Y.Z.devN` 改为 `X.Y.Z`
- `CHANGELOG.md` 顶部新增本版本条目（Added / Changed / Fixed / Release Evidence 四段式）
- `README.md` / `README.zh-CN.md` 中的工具数、Tier-1 列表、特性段同步
- `PRIVACY.md` 中的工具数同步（如有变化）
- `test_packaging.py` 中的 floor 数字（工具数）同步

### 1.3 防御性文档的"反向暴露"自检

> 这条经常被忽略 — 你**为了防泄漏而写的文档本身可能在泄漏**。

发版前用"对手视角"读以下文件，问"如果我是竞品工程师，从这段文字能推断出什么"：

| 文件 | 反向暴露的典型陷阱 |
|------|------------------|
| `docs/release-playbook.md`（本文件） | "历史教训"段落 = 自供以前 commit 过敏感内容；过往措辞示例 = 给对手 reverse engineer 自己定位 |
| `.github/workflows/guard-*.yml` | 注释里写"为什么加这个防护" = 间接告诉对手"过去犯过什么错"；BLOCKED 数组的内联分类注释 = 给对手"哪些路径有戏可挖"的地图 |
| `CHANGELOG.md` 当前版本条目 | 内部 review 编号（H1-Mn / R1-Rn 等）= 暴露内部审计流程；详列具体 bug 类别 = 自身弱点清单；"以前没做 X，现在做了" = 自供过去缺位 |
| `SECURITY.md` / `PRIVACY.md` | 详细解释"为什么这个威胁要防" = 等于公开 threat model |
| commit message | "fix bug found by audit" = 暴露内部 audit 流程 |

**修复模式**：把"为什么"留在私有笔记，文档只写"是什么/怎么做"。
- ❌ "因为 v3.x 出过 Y 问题，所以新增 Z 防护"
- ✅ "新增 Z 防护"
- ❌ "M3 修复：doctor PreCompact hook 要求 module 名和 env 标记都存在（之前只查 module 名导致半坏 hook 误判 ok）"
- ✅ "doctor hook 检查更严格，避免半配置的 hook 被误判通过"

---

## 2. 脱敏清理（**强制**，发布前最后一关）

### 2.1 为什么这步不能跳

Engram 是开源仓库 + 公开发布，仓库内容会进入：
- GitHub 公开页面
- PyPI 源码包（`sdist`）
- 第三方镜像（archive.org、深度学习训练语料、内容农场）

一旦敏感内容入了 git 历史，**事后清理需要重写历史 + force push + 通知所有 fork**——代价远高于"发布前 5 分钟检查"。

### 2.2 五层脱敏检查

| 层 | 范围 | 检查方法 | 失败时怎么办 |
|---|---|---|---|
| **L1 文件层** | 工作区文件 | `git status` + `git ls-files` 看有没有不该入仓的文件 | `git rm` + 放到仓库外 |
| **L2 内容层** | 已跟踪文件的内容 | 关键词扫描（见 §2.3） + `scripts/release_sanitize_check.py` | 修改文件移除敏感内容 |
| **L3 Commit 消息层** | `git log` 文本 | `git log --all --format="%s%n%b" \| grep -iE <patterns>` | 若已 push 需历史重写（见 §8） |
| **L4 .gitignore 层** | 持续防护 | 高风险路径模式已加进 `.gitignore` | 加规则 + 验证 `git check-ignore <path>` |
| **L5 CI guard 层** | Push 后自动拦截 | `.github/workflows/guard-strategic-files.yml` 的 `BLOCKED` 数组 | guard 触发后改 .gitignore + 重新提 PR |

五层是**纵深防御**而不是冗余 — 任一层漏掉，下一层兜底。本地维护者用 L1-L2-L4，CI 用 L5 防协作者手滑，L3 是历史扫描（适合定期审计）。

### 2.3 必扫敏感模式

**第一类：凭据与个人信息**（technical secrets）

| 类别 | 示例 | 处置 |
|---|---|---|
| **API key / token** | `sk-...`、`gho_...`、`ghp_...`、`pypi-...`、`hf_...`、`xox[abprs]-...`、AWS `AKIA...`、长十六进制串 | 立即从代码 / 配置中移除，改用环境变量；若已 commit → 撤销该 key + 历史重写 |
| **账号 / 密码** | 数据库连接串、SMTP 凭据、平台账号密码、`password=...` | 同上 |
| **私钥 / 证书** | `BEGIN PRIVATE KEY` / `BEGIN OPENSSH PRIVATE KEY` 头部、`.pem` / `.p12` | 不允许入仓 |
| **本地绝对路径** | `C:\Users\<姓名>\...`、`/home/<姓名>/...` | 用 `~/` 或环境变量代替；测试 / 示例数据里改成 `tmp_path` 或 `<USER>` 占位符 |
| **真实邮箱 / 手机号** | 个人邮箱、工作邮箱 | 用占位符（`user@example.com`） |

**第二类：战略与弱点暴露**（strategic disclosure）

> 这类不像 API key 那样"明显敏感"，但同样**不应该入公开仓库** — 它们的杀伤力在于"给对手免费做了情报作业"。

| 类别 | 典型物件 | 风险 | 处置 |
|---|---|---|---|
| **竞品 / 友商内部信息** | 竞品代号、未公开战略、与具体公司的来往细节、市场分层图、对手 stars/下载量调研 | 给对手"知己知彼"的工具 | 改用通用类别描述（"agent memory tools"、"vector DB 方案"）；详见 §2.4 |
| **核心未公开思路** | 长期产品愿景文档、营销话术 source of truth、未公开的差异化路径 | 给对手抄你的牌 | 留在私有笔记 / 本地知识库 |
| **路线图细节** | Phase 1/2/3 完整 roadmap、长期里程碑、"v3.31+ 要做 X"的承诺 | 锁死自己 + 让对手提前布防 | 公开版只写"近期方向"（1-2 个版本内） |
| **自评 / 外部评测报告** | external AI 评测分数、自评 vs 实测对比、跨 AI cross-validation 报告 | 自己的 weak spots audit 上交对手 | 评测原始报告不入仓；只在 release notes 写"通过 X 项测试"等中性结论 |
| **覆盖率 / 测试缺口** | `coverage_baseline_*.md` 里的 "Remaining gaps / hard-to-reach code" 段 | 攻击面地图 — 告诉对手"哪些路径没测可能能 bypass" | 不入仓；只对外公开"总覆盖率 X%" |
| **设计 rationale 文档** | "为什么这样设计 / 设计思路 / 设计 trade-off" 类文档 | 把核心 insight 全暴露 | docstring 里可写技术性 trade-off；战略 trade-off 留私有 |
| **内部 review 流程信息** | review 编号（H1-Mn / R1-Rn）、跨 AI 审查工具组合、内部 audit 频率 | 暴露内部流程 + 让对手知道你怎么找自己的 bug | release notes 里描述用户能感知的变化，不暴露内部审计编号 |
| **招募 / 冷启动策略** | 内测招募草稿、社区切入话术 | 给对手抢你的渠道 | 留私有 |
| **内部代号** | 私有项目 / 团队 / 内部里程碑代号 | 信息片段反向关联 | 改成对外名称 |
| **反向自供式叙述** | "我们以前做错了 X 所以现在做 Y"、"v3.x 历史教训" | 等于自供过去 commit 过敏感内容 | 改成中性"是什么/怎么做"（不解释"为什么需要"） |

### 2.4 比较 / 核心思路的安全表述

> 红线：**比较可以做，绝对化表述、贬损、内部情报不可以**。

通用原则：
- 用**类别**而不是**具体公司名**做对比（"vector DB 方案"而不是某厂商）
- 描述差异而不是优劣（"解决的问题不同"而不是"我们更好"）
- 避免绝对化表述（用"我们调研过的项目中"而不是"没有任何工具能"）
- 不写第三方的非公开商业信息、不引用第三方未公开内容

具体措辞参考 `docs/comparison.md`。

### 2.5 推荐扫描命令

**主入口：`scripts/release_sanitize_check.py`**

```bash
# 普通扫描（HIGH 命中 → 退出 1；warn 命中 → 退出 0）
python scripts/release_sanitize_check.py

# 严格模式（warn 也阻断）—— 发版前用
python scripts/release_sanitize_check.py --strict

# 包含 commit 消息扫描（慢一些）
python scripts/release_sanitize_check.py --commit-messages --strict
```

此脚本：
- 内置 9 种 HIGH / warn 模式（API key、PEM、Windows/POSIX 路径、`password=` 等）
- 读取 `~/.engram-release-sensitive.txt`（本地敏感词清单，**不入仓**，每位维护者自己维护）
- 已接入 `.github/workflows/publish.yml`，发 PyPI 前强制跑一次，HIGH 命中阻断发布

**额外的兜底 grep（手工应急用）：**

```bash
# 1) commit 消息扫描（脚本默认不扫，--commit-messages 启用）
git log --all --format="%s%n%b" | grep -iE "password|secret|token|api[_-]?key"

# 2) 战略文件 ad-hoc 检查（guard workflow 也会拦，但本地可预扫）
git ls-files | grep -iE "milestone_review|coverage_baseline|evaluations/v.*/(REPORT|evidence)|design/|telemetry_roadmap|playbook-auto|messaging|vision|competitive_landscape|beta_recruitment"
```

> 本地敏感词清单（`~/.engram-release-sensitive.txt`）维护示例：每行一个词或正则。建议含你的真实用户名、内部代号、合作公司名等机器特定 / 关系特定的词。**不要 commit 这个文件本身**。

### 2.6 命中后的处置

按"是否凭据级"和"是否已 push"分四档：

| 状态 | 凭据 / secret 类 | 战略 / 文档暴露类 |
|------|----------------|------------------|
| **未 commit** | 改文件 + 重跑测试 | 改文件，可顺便加 `.gitignore` 规则 |
| **已 commit 未 push** | `git reset --soft HEAD~N` → 修正 → 重新 commit | 同左；可一次 commit 修多个 |
| **已 push（轻量）** | 立即轮换凭据 + 评估范围 + 历史重写（§8） | 当前清理 + `.gitignore` + CI guard 兜底；视严重度决定是否历史重写 |
| **已 push（凭据已泄漏）** | 同上 + release notes 模糊化（"凭据已轮换"，不指路） | 不太适用 |

**判断历史重写值不值得**（见 §8）：

| 信号 | 倾向重写 | 倾向不重写（加 CI guard 防未来） |
|------|---------|----------------------------|
| 是 critical secret（API key / 私钥） | ✅ 必须重写 | — |
| 是战略文档（路线图 / 评测报告） | ⚠️ 看 stars 数 + fork 数 | ✅ 1000 stars 以下 + 少 fork |
| 仅是 commit message 措辞问题 | ❌ 重写代价大于收益 | ✅ |
| 已被 archive.org 抓取 | ⚠️ 重写也救不回 archive | ✅ 至少阻断未来访问 |

---

## 3. Release commit 与 tag

```bash
git add -A
git commit -m "release(vX.Y.Z): <一句话主题>"
git tag vX.Y.Z
git push origin main --tags
```

> **不要** force push 到 main（除非 §2.6 的历史重写场景，且已通知所有维护者）。

---

## 4. GitHub Release

```bash
gh release create vX.Y.Z \
  --title "vX.Y.Z — <主题>" \
  --notes "$(awk '/^## \[X.Y.Z\]/,/^## \[/' CHANGELOG.md | head -n -1)"
```

`publish.yml` 会自动触发 PyPI 发布。

---

## 5. 推送后文档同步（Post-Push Doc Sync）

发版后建议维护的下游同步：

- 任何包含版本号 / 测试数 / star 数等"易变数字"的本地文档
- 任何引用 piia-engram 版本的 manifest / lockfile
- 沉淀关键经验 / 决策到 Engram（`add_lesson` / `add_decision`），下次发版可参考

---

## 6. 应急回滚

- **PyPI**：已发布的版本无法删除，只能 `pip yank`（`gh-action-pypi-publish` 不支持，需手动到 PyPI 网页操作）。
- **GitHub Release**：`gh release delete vX.Y.Z`
- **Tag**：`git push origin :refs/tags/vX.Y.Z`（远端） + `git tag -d vX.Y.Z`（本地）

回滚后立即发布修复版（`vX.Y.Z+1`），而不是再次复用同版本号。

---

## 7. 这份 playbook 自己的脱敏

⚠️ 这份文档现在就是公开的 — **不要往这里塞真实的竞品名、内部代号、本地路径、客户名**。如果需要更具体的内部清单，维护在私有笔记 / Engram 本地知识里，用 `add_decision` 或 `add_lesson` 持久化，对仓库零暴露。

同样不要在这里写"我们以前因为 X 出过 Y 问题所以现在加 Z 防护" — 那是反向自供。流程文档只描述**现在怎么做**，不描述**为什么需要**。"为什么"留在私有 Engram 知识库。

---

## 8. 历史重写（git filter-repo）完整流程

### 8.1 触发条件

满足任一即应启动：

- 凭据级 secret（API key / 私钥 / 密码）已 push 到公开仓库
- 战略性文件（路线图 / 评测报告 / weakness audit / 设计 rationale）已被 .gitignore 或 git rm 但**历史里还能翻到**
- §1.3 "反向暴露自检"发现多个文件含自供式叙述

### 8.2 不会受影响的渠道

执行前先确认这些**不需要重新发布**：

| 渠道 | 是否受影响 | 为什么 |
|------|---------|--------|
| **PyPI** | ✅ 不受影响 | sdist 是构建时快照，本来就不含被删的文件 |
| **MCP Registry** | ✅ 不受影响 | 只存 `server.json`，不存代码 |
| **Glama** | ✅ 自动同步 | 24h 内自动检测到 GitHub 新状态 |
| **GitHub Release** | ✅ 自动跟随新 tag | release 通过 tag name 关联，不是 commit hash；force push tag 后 release.targetCommitish 自动更新 |

唯一无法消除的：archive.org / Software Heritage 等第三方镜像可能保留过期快照（**追不回**，只能阻断未来访问）。

### 8.3 执行步骤

```bash
# === Step 0：完整 mirror backup ===
rm -rf /tmp/repo-prefilter-backup
git clone --mirror . /tmp/repo-prefilter-backup
# 验证：cd /tmp/repo-prefilter-backup && git log --oneline -3

# === Step 1：安装 git-filter-repo（如尚未装）===
# git-filter-repo 不是 git 内置，需 pip
python -m pip install git-filter-repo

# === Step 2：跑 filter-repo 抹除文件 ===
# --invert-paths + 多个 --path 反向移除文件列表
# --path-glob 支持通配
python -m git_filter_repo \
  --invert-paths \
  --path docs/private/some_file.md \
  --path-glob 'experiments/competitive_*' \
  --force

# === Step 3：验证 ===
# 对每个被删文件检查历史 commits
git log --all --oneline -- docs/private/some_file.md
# 期望：空输出（0 commits）

# === Step 4：重加 origin ===
# filter-repo 默认会移除 origin 防止意外 force push
git remote add origin https://github.com/<owner>/<repo>.git

# === Step 5：跑测试确认代码还能跑 ===
pytest tests/ -q

# === Step 6：force push main ===
git push --force origin main

# === Step 7：force push 所有 tag（tag hash 全变了）===
git push --force --tags origin

# === Step 8：验证远端 ===
gh api repos/<owner>/<repo>/contents/docs/private/some_file.md  # 期望 404
gh release view vX.Y.Z --json tagName,targetCommitish  # 应自动跟随新 hash
```

### 8.4 不可逆后果

- 所有 commit hash 改变 → 任何外部链接到具体 commit 的引用失效
- 所有 tag hash 改变 → 任何 fork（如有）都需要重新 rebase
- archive.org 抓的旧快照保留，无法删
- 已被收录到训练语料 / 内容农场的快照，无法删

### 8.5 备选：不重写历史，仅加 CI guard

当历史重写代价过大（高 stars 项目、活跃 fork 社区）时，**只清当前 + 加 CI guard** 是合理折中：

- 当前清理：`git rm` + 加 `.gitignore`
- 加 CI guard：在 `.github/workflows/` 加 workflow 检查 BLOCKED 路径模式
- 接受"git history 里有早期版本"的事实，靠"未来发布更干净 + 当前文档权威"补救

行业惯例（Mem0 / Letta / Postgres 等）都不追溯重写 — 这不是问题，只要现在的 README 和最新 release 是干净的，绝大多数用户和评估者只看当前状态。
