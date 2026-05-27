# Release Playbook

发布 piia-engram 新版本的完整流程。每次 `git push` + `gh release create` 之前过一遍这份清单。

> **历史教训**：v3.13/v3.29 系列曾因仓库历史里残留竞品名、内部战略思路、本地路径、临时 token 等内容，事后不得不做 `git filter-repo` 历史重写。这份 playbook 的存在就是为了**让脱敏成为发布的常规一步**，而不是事后补救。

---

## 0. 触发时机

- **GitHub Release**：每 ~3 天发一次（用户偏好节奏）。
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

---

## 2. 脱敏清理（**强制**，发布前最后一关）

### 2.1 为什么这步不能跳

Engram 是开源仓库 + 公开发布，仓库内容会进入：
- GitHub 公开页面
- PyPI 源码包（`sdist`）
- 第三方镜像（archive.org、深度学习训练语料、内容农场）

一旦敏感内容入了 git 历史，**事后清理需要重写历史 + force push + 通知所有 fork**——代价远高于"发布前 5 分钟检查"。

### 2.2 四层脱敏检查

| 层 | 范围 | 检查方法 |
|---|---|---|
| **L1 文件层** | 工作区文件 | `git status` + `git ls-files` 看有没有不该入仓的文件 |
| **L2 内容层** | 已跟踪文件的内容 | 关键词扫描（见 2.3） |
| **L3 Commit 消息层** | `git log` 文本 | `git log --all --format="%s%n%b" | grep -iE <patterns>` |
| **L4 .gitignore 层** | 持续防护 | 高风险目录 / 文件已加进 `.gitignore`，避免下次手滑 |

### 2.3 必扫敏感模式

| 类别 | 示例 | 处置 |
|---|---|---|
| **API key / token** | `sk-...`、`gho_...`、`ghp_...`、`pypi-...`、`hf_...`、长十六进制串 | 立即从代码 / 配置中移除，改用环境变量；若已 commit → 撤销该 key + 历史重写 |
| **账号 / 密码** | 数据库连接串、SMTP 凭据、平台账号密码 | 同上 |
| **私钥 / 证书** | `BEGIN PRIVATE KEY` / `BEGIN OPENSSH PRIVATE KEY` 头部、`.pem` / `.p12` | 不允许入仓 |
| **本地绝对路径** | `C:\Users\<姓名>\...`、`/home/<姓名>/...` | 用 `~/` 或环境变量代替；测试里改成 `tmp_path` |
| **真实邮箱 / 手机号** | 个人邮箱、工作邮箱 | 用占位符（`user@example.com`） |
| **竞品名 / 友商内部信息** | 竞品的代号、未公开战略、与具体公司的来往细节 | 改用通用类别描述（"agent memory tools"、"vector DB 方案"）；详见 §2.4 |
| **核心未公开思路** | 尚未在 README/CHANGELOG 公开的产品方向、长期路线图 | 留在私有笔记 / Engram 本地记忆里，不进仓库文档 |
| **内部代号** | 私有项目 / 团队 / 内部里程碑代号 | 改成对外名称 |

### 2.4 竞品 / 核心思路的安全表述

> 红线：**比较可以做，绝对化表述、贬损、内部情报不可以**。

| ❌ 不要这样写 | ✅ 改成这样 |
|---|---|
| "X 公司的方案有 bug" | "vector DB 方案在小语料场景下召回率偏低" |
| "我们要替代 X" | "Engram 与 X 解决的问题不同：X 是 agent memory，Engram 是 user identity" |
| "没有任何工具能做到 X" | "Among the projects we've surveyed, piia-engram is the only one using X"（R2 修复模式） |
| "X 在融资 Y 美元" | 不写 |
| 引用竞品未公开的源码 / 内部文档 | 不写 |

具体的措辞示例参考 `docs/comparison.md`——这是经过五方审查 + R2 修复的"可证伪表述"基线。

### 2.5 推荐扫描命令

```bash
# 在仓库根目录运行（PowerShell / bash 通用）

# 1) API key 形态
git grep -nE "(sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|pypi-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,})"

# 2) 私钥
git grep -n "BEGIN.*PRIVATE KEY"

# 3) 本地路径（按你机器的实际盘符 / 用户名调整）
git grep -nE "C:\\\\Users\\\\[A-Za-z0-9_-]+|/home/[a-z]+"

# 4) commit 消息扫描
git log --all --format="%s%n%b" | grep -iE "password|secret|token|api[_-]?key"

# 5) 自定义敏感词（你的本地清单，不入仓）
# 维护在 ~/.engram-release-sensitive.txt（每行一个词），扫描脚本：
test -f ~/.engram-release-sensitive.txt && \
  git grep -niE "$(paste -sd '|' ~/.engram-release-sensitive.txt)"
```

> 本地敏感词清单（`~/.engram-release-sensitive.txt`）**不进仓库**，每个维护者自己维护。这里只放扫描脚本的模板。

### 2.6 命中后的处置

- **未 commit**：直接修改文件，重跑测试。
- **已 commit 但未 push**：`git reset --soft HEAD~N` → 修正 → 重新 commit。
- **已 push**：
  1. 立即撤销 / 轮换涉事凭据（API key、token、密码）
  2. 评估影响范围（哪些用户 fork 了、archive 是否抓取）
  3. 用 `git filter-repo` 重写历史 → force push → 删除受影响的旧 tag / branch
  4. 在 release notes 里**不要**直接描述泄漏内容（避免给好奇者指路），只说"敏感凭据已轮换"

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

工作空间根目录 `CLAUDE.md` 已定义"推送后文档同步规则"——这里只重复关键项：

- `PROJECT_REGISTRY.md` 顶部 auto-status 数字（版本 / 测试数 / stars / 日期）
- `LOCAL_TOOLS_REGISTRY.md` 中 `piia-engram` 版本
- 重大事件加进 PROJECT_REGISTRY 第 10.2 / 11 / 11.5 节
- 沉淀关键经验 / 决策到 Engram（`add_lesson` / `add_decision`）

---

## 6. 应急回滚

- **PyPI**：已发布的版本无法删除，只能 `pip yank`（`gh-action-pypi-publish` 不支持，需手动到 PyPI 网页操作）。
- **GitHub Release**：`gh release delete vX.Y.Z`
- **Tag**：`git push origin :refs/tags/vX.Y.Z`（远端） + `git tag -d vX.Y.Z`（本地）

回滚后立即发布修复版（`vX.Y.Z+1`），而不是再次复用同版本号。

---

## 7. 这份 playbook 自己的脱敏

⚠️ 这份文档现在就是公开的 — **不要往这里塞真实的竞品名、内部代号、本地路径、客户名**。如果需要更具体的内部清单，维护在私有笔记 / Engram 本地知识里，用 `add_decision` 或 `add_lesson` 持久化，对仓库零暴露。
