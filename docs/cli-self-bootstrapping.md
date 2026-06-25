# CLI 自举与引导性设计审计

**日期:** 2026-06-25
**状态:** 草案
**前置阅读:** [cli-ai-first-audit.md](cli-ai-first-audit.md) · [product-vision.md](product-vision.md)

---

## 自举的定义

"CLI 自举" 是指：一个完全不了解 PeerPedia 的人（或 AI agent），仅通过与 CLI 交互，就能学会使用全部功能。不需要外部文档。

这要求四个维度全部到位：

| 维度 | 含义 | 当前状态 |
|------|------|---------|
| **可发现性** | 能不能找到想用的命令？ | ⚠️ 有 argparse `--help`，但结构扁平，18 个顶层命令没有按使用场景组织 |
| **可学习性** | 看了 help 能不能学会怎么用？ | ❌ 没有示例，没有教程，没有入门引导 |
| **错误恢复** | 出错了能不能知道怎么修？ | ⚠️ 约 30% 的错误消息带引导，70% 只陈述问题 |
| **可查询性** | AI agent 能不能程序化发现命令 schema？ | ❌ 只有人工可读的 `--help` 文本，无结构化 schema 端点 |

---

## 一、可发现性：`--help` 重构

### 当前问题

18 个顶层命令 + 子命令全部平铺在 `--help` 里。用户打开帮助后看到的是**命令字典**，不是**使用指南**。

```
peerpedia --help
→ 18 个命令，按字母排序。看不出先做什么、后做什么、哪些是常用。
```

新手真正需要的是按**使用场景**组织的引导，而不是按字母排序的字典。

### 改进方案：三层 help

```
peerpedia --help          → 场景导向的顶层概览（入门 → 日常 → 协作 → 管理）
peerpedia <cmd> --help    → 传统 argparse，但必须有 EXAMPLES 段
peerpedia <cmd> --help    → 加 --examples 只输出示例
```

### 顶层 `--help` 应该是这样的

```

  PeerPedia — AI-driven academic publishing from the terminal.

  GETTING STARTED
    account register       Create your identity
    account login          Sign in to an existing account
    article create         Write your first paper
    ?Mother                Ask the AI guide anything

  DAILY WORKFLOW
    article list           Browse papers (--feed, --mine, --search)
    article show           Read a paper and its reviews
    review submit          Peer-review a paper
    notifications          See what's new

  PUBLISHING
    article publish        Submit to the sedimentation pool
    article edit           Revise your draft
    article scan           Trigger sedimentation → published

  COLLABORATION
    fork                   Copy a published paper to start your version
    merge propose          Propose merging your changes back
    maintainer add         Invite a co-author

  NETWORK
    follow                 Follow a researcher
    sync status            Check peer server connection
    sync push              Send your changes to the network

  Run 'peerpedia <command> --help' for detailed options.
  Run 'peerpedia <command> --examples' for usage examples.
  Type 'peerpedia' with no arguments to enter the REPL.
```

每个场景组有 3-4 个最核心的命令。不是 18 个全列——太多等于没有。

### 子命令 `--help` 必须加 EXAMPLES 段

当前：

```
$ peerpedia article create --help
usage: peerpedia article create [-h] --title TITLE [--format {markdown,typst}]
                                [--content CONTENT] [--no-editor] [--publish]
                                [--scores SCORES] [--json]

Create a new article.

options:
  --title TITLE    Article title
  --format ...     Source format
  ...
```

应该：

```
$ peerpedia article create --help

  Create a new article.  Opens your editor by default; use --content
  to skip the editor.

  OPTIONS
    --title TITLE          Article title (required)
    --content CONTENT      Article body in Markdown or Typst
    --format {markdown,typst}  Source format (default: markdown)
    --no-editor            Skip the editor (when --content is not enough)
    --publish              Publish immediately after creation
    --scores SCORES        Self-review scores for immediate publish
                           Format: orig=4,rigor=3,comp=4,ped=3,imp=3
    --json                 Machine-readable output

  EXAMPLES
    # Write interactively
    peerpedia article create --title "Quantum Error Correction"

    # Create with inline content
    peerpedia article create --title "Introduction" --content "# Hello\n\nWorld."

    # Create and publish immediately
    peerpedia article create --title "My Paper" --content "# Abstract" \
        --publish --scores "orig=4,rigor=3,comp=4,ped=3,imp=3"

  SEE ALSO
    article edit       Revise your draft
    article publish    Submit to sedimentation pool
    article list       Browse existing articles
```

**SEE ALSO 是关键**——它告诉用户"如果你做完了这件事，下一步应该看什么"。这是自举的核心：命令之间的导航。

---

## 二、可学习性：内置教程和示例

### 新增：`--examples` flag

每个命令支持 `--examples`，只输出用法示例，简洁直接，供 AI agent 快速学习。

```
$ peerpedia article publish --examples

  # Publish a draft with self-review
  peerpedia article publish abc12345 \
      --scores "orig=4,rigor=3,comp=4,ped=3,imp=3"

  # The article enters the sedimentation pool. After 3 days,
  # it becomes published. Check status with:
  peerpedia article show abc12345
```

### 新增：`peerpedia intro` 或改进 `?Mother`

当前的 `?Mother` 输出一个 Rich Panel 的纯文本指南——对新手有用，但它是**静态的**，不会根据用户状态变化。

改进方案：`peerpedia intro` 或改进的 `?Mother` 应该：

1. **检测用户状态**：有没有注册？有没有论文？有没有待审稿？
2. **给出个性化引导**："你还没有注册，我带你完成。输入你的名字："
3. **交互式教程**：不是一次性输出 100 行指南，而是一步步来，每次只问一件事

```
$ peerpedia intro

  Welcome to PeerPedia! I'll help you get started.

  First, let's create your identity. What's your name?
  > Chenqi Meng

  Great, Chenqi. Now choose a password:
  > ****

  You're all set! Here's what you can do next:

  1. Write your first paper: peerpedia article create --title "My Paper"
  2. See what others are reading: peerpedia article list --feed
  3. Ask me anything: peerpedia ?Mother "how do I publish?"

  Type 'peerpedia intro --next' for step 2.
```

### 新增：`peerpedia explain <command>`

输出一个命令的**教学版说明**，比 `--help` 更口语化，包含"为什么需要这个命令"和"什么时候用"。

```
$ peerpedia explain sedimentation

  Sedimentation is PeerPedia's quality control mechanism.
  When you publish a paper, it doesn't go live immediately. Instead,
  it enters a 3-day "sedimentation pool" where other researchers can
  review it. This prevents spam and ensures every published paper has
  been seen by human eyes.

  Related commands:
    article publish    Submit your paper to the pool
    article scan       Check if any papers have finished sedimentation
    review submit      Review papers currently in the pool
```

---

## 三、错误恢复：每个错误必须引导下一步

### 当前审计结果

审查了所有 `_die` 调用点（约 50 个），按引导质量分类：

| 质量 | 数量 | 示例 |
|------|------|------|
| 🟢 带引导 | ~15 | `"No user specified. Register first:\n  peerpedia account register --name <your-name>"` |
| 🟡 陈述问题 | ~25 | `"Article not found"`、`"Wrong password"`、`"Server unreachable"` |
| 🔴 纯技术信息 | ~10 | `"User 'xxx' not found — DB inconsistency"`、`"DB has reviews but no reviews/ directory on disk"`、无引导的 `traceback.print_exc()` |

### 改进原则

每个错误消息必须回答三个问题：

1. **发生了什么？**（事实陈述）
2. **为什么？**（原因，如果可知）
3. **下一步做什么？**（可操作的修复命令）

### 具体改进清单

| 当前消息 | 问题 | 改进后 |
|---------|------|--------|
| `"Wrong password."` | 只陈述，无引导 | `"Wrong password. If you forgot it, an admin can reset your salt. If this is a new device, use 'account bootstrap' first."` |
| `"Server unreachable"` | 无建议 | `"Cannot reach the peer server. Check: (1) is 'PEERPEDIA_SERVER' set? (2) is the server running? (3) is your network up? Run 'sync status' to diagnose."` |
| `"User 'xxx' not found — DB inconsistency."` | 纯技术信息，对用户无用 | `"Your session references a user that no longer exists. This is an internal inconsistency. Try 'account recover' or 'account register'."` |
| `"Article not found"` | 无建议（但 `_resolve_article_id` 里已经有好了） | ✅ 已有 `"Try a title keyword or article ID prefix."` |
| `"DB has reviews but no reviews/ directory on disk"` | 纯技术信息 | `"The article's review data is incomplete — DB records exist but the git repository is missing review files. Try 'sync pull' from the original peer."` |
| `"Aborting: empty commit message."` | 无引导 | `"Your commit message was empty. Use --message 'your message' to provide one, or set your EDITOR and write a message interactively."` |
| `"No source file found for article xxx"` | 无引导 | `"The article record exists but its source file is missing from disk. This may happen if the git repo was not fully synced. Try 'sync pull' or contact the article's maintainer."` |
| `"--status draft requires --mine"` | 无解释 | `"Drafts are private. Use --mine to see only your own drafts, or omit --status to see published articles."` |

### `_die` 增强

当前 `_die(msg)` 只有 message。应该扩展第二个参数：

```python
_die(
    "Wrong password.",
    code="NOT_AUTHORIZED",
    suggestion="If you forgot your password, run 'account recover'. "
               "If this is a new device, run 'account bootstrap' first.",
    see_also=["account recover", "account bootstrap"],
)
```

在 `--human` 模式下渲染为：

```
✗ Wrong password.

  If you forgot your password:  peerpedia account recover
  If this is a new device:      peerpedia account bootstrap

  Related: account recover · account bootstrap
```

---

## 四、可查询性：AI agent 的 schema 发现

### 新增：`peerpedia schema`

输出所有命令的 JSON Schema，供 AI agent 做 function calling。

```json
$ peerpedia schema
{
  "version": "1.0",
  "commands": [
    {
      "name": "article_create",
      "description": "Create a new article as a draft",
      "cli": "peerpedia article create --title <str> [--content <str>] [--format markdown|typst] [--no-editor] [--publish] [--scores <str>]",
      "parameters": {
        "title": {"type": "string", "required": true, "description": "Article title"},
        "content": {"type": "string", "required": false, "description": "Article body in Markdown or Typst"},
        ...
      },
      "returns": {"article_id": "string", "status": "draft", "commit_hash": "string"},
      "errors": ["NOT_FOUND", "BAD_REQUEST", "NOT_AUTHORIZED"],
      "preconditions": ["authenticated"],
      "idempotent": false,
      "workflow_before": ["account register"],
      "workflow_after": ["article edit", "article publish"]
    },
    ...
  ]
}
```

**`workflow_before` 和 `workflow_after`** 是关键——它们让 AI agent 理解命令之间的依赖关系。如果 AI 尝试 `article publish` 但没有先 `article create`，它能从 schema 里看到。

### 新增：`peerpedia schema <command>`

只输出一个命令的 schema，用于动态 tool registration（见 [cli-as-ai-tool.md](cli-as-ai-tool.md) Level 3）。

### 实现路径

`peerpedia schema` 从 `parser.py` 的 `COMMAND_GROUPS` + 一份轻量级的 `command_metadata.json` 生成。parser 定义参数，metadata 定义 workflow 关系、返回值 schema、错误码。

---

## 五、其他自举改进

### `peerpedia status`

一个命令，告诉用户"系统现在是什么状态"：

```
$ peerpedia status
  Logged in as:  Chenqi Meng (abc12345)
  My drafts:     2
  In sedimentation: 1
  Published:     3
  Pending reviews:  1
  Unread notifications: 2
  Server:        https://peer.example.com (online)
  Pending sync:  0

  What next?
  → Continue writing:      peerpedia article edit <id>
  → Review a paper:        peerpedia article list --feed
  → Check notifications:   peerpedia notifications
```

这是用户每次打开终端时应该看到的第一件事。

### `peerpedia workflow <goal>`

用户描述目标，CLI 输出命令序列：

```
$ peerpedia workflow "publish a paper"
  1. peerpedia article create --title "..."     ← write your draft
  2. peerpedia article edit <id>                ← revise until ready
  3. peerpedia article publish <id> --scores "orig=4,..."
  4. peerpedia article scan                     ← after 3 days, promote to published
```

### Tab 补全增强

当前已经有 argcomplete 支持。增强方向：
- 补全已有 article ID/前缀
- 补全已关注用户的 @name
- 补全分数维度

### 确认模式 (--dry-run)

在破坏性操作前预览结果（已在 cli-ai-first-audit.md 中讨论）。

---

## 六、改动量估算

| 改动 | 涉及文件 | 工作量 |
|------|---------|--------|
| 三层 help 重构 | `parser.py` | 1 天 |
| EXAMPLES 段（每个命令） | `parser.py` + 各 handler docstring | 1 天 |
| SEE ALSO 段 | `parser.py` + 元数据文件 | 半天 |
| `_die` 加 suggestion/see_also | `helpers.py` + 约 50 个调用点 review | 1 天 |
| `peerpedia intro` 交互式教程 | 新建 `cli/handlers/intro.py` | 1 天 |
| `peerpedia explain <topic>` | 新建 `cli/explain.py` + 知识库 | 1 天 |
| `peerpedia schema` | 新建模块 + `command_metadata.json` | 1 天 |
| `peerpedia status` | 新建 `cli/handlers/status.py` | 半天 |
| `peerpedia workflow <goal>` | 新建模块 + 工作流定义 | 1 天 |
| Tab 补全增强 | `cli/parser.py` | 半天 |

**总计约 7-8 天。优先级：`_die` 引导 → schema → help 重构 → intro → 其余。**

---

## 七、自举检查清单

一个真正自举的 CLI，标准是：

- [ ] `peerpedia --help` 后，新手能在 30 秒内决定下一步做什么
- [ ] 每执行三个命令，遇到一个错误——这个错误必须告诉你怎么修
- [ ] `peerpedia <cmd> --help` 看完，新手能写出至少一个正确用法
- [ ] AI agent 能通过 `peerpedia schema` 获得完整的机器可读命令定义
- [ ] 命令之间有导航（SEE ALSO、workflow_before/after）
- [ ] 有两个教程入口：`peerpedia intro`（交互式）和 `peerpedia schema`（程序式）
- [ ] 每个破坏性操作都有一个安全预览路径（--dry-run）

---

## 参考

- [cli-ai-first-audit.md](cli-ai-first-audit.md) — AI-first 重构审计
- [cli-as-ai-tool.md](cli-as-ai-tool.md) — CLI as AI tool 设计
- [product-vision.md](product-vision.md) — 产品愿景
