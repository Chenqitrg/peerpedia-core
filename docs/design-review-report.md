# CLI 设计审查报告

> **Status: HISTORICAL (2026-06-24).** This was a one-time code review snapshot.
> Some findings have been addressed since (tab completion wired, help handler added,
> _ok messages in create paths). A new review would be needed for current state.

**日期:** 2026-06-24
**分支:** main
**审查范围:** peerpedia-core CLI 工具（命令结构、交互设计、错误处理、帮助文档、REPL 体验）
**审查方法:** 逐文件代码审查 + 用户视角走查

---

## 总览评分

| 维度 | 评分 | 状态 |
|------|------|------|
| 命令结构与分组 | 4/10 | 🔴 严重 |
| 帮助文档质量 | 3/10 | 🔴 严重 |
| 错误处理体验 | 3/10 | 🔴 严重 |
| 成功反馈一致性 | 5/10 | ⚠️ 不足 |
| REPL 体验 | 5/10 | ⚠️ 不足 |
| 命令发现性 | 2/10 | 🔴 严重 |
| 输出格式 | 6/10 | ⚠️ 一般 |
| 交互确认与安全 | 4/10 | 🔴 严重 |
| **综合** | **4/10** | 🔴 |

---

## 1. 命令结构与分组 — 4/10

### 1.1 顶层命令 vs 子命令分组不一致

当前结构：

```
peerpedia fork          ← 顶层命令
peerpedia follow        ← 顶层命令
peerpedia unfollow      ← 顶层命令
peerpedia compile       ← 顶层命令
peerpedia bookmark add  ← 子命令组
peerpedia merge propose ← 子命令组
peerpedia following     ← 空子命令名的子命令组
peerpedia followers     ← 空子命令名的子命令组
```

**问题：** `fork`、`follow`、`unfollow` 是顶层命令，但语义相关的 `bookmark add/remove`、`merge propose/accept` 却在子命令组下。用户无法从命名模式推断一个操作属于哪一层。

`following` 和 `followers` 使用了空字符串作为子命令名（`add_parser("", ...)`），导致语法为 `peerpedia following --user X` 而非 `peerpedia following list --user X`。argparse 处理空子命令名的行为依赖实现细节。

**10/10 的样子：** 一致的分组策略。两种合理方案：
- A) 全部扁平化：`peerpedia fork`、`peerpedia follow`、`peerpedia bookmark`、`peerpedia merge`
- B) 全部分组：`peerpedia social follow`、`peerpedia social unfollow`、`peerpedia bookmark add`、`peerpedia merge propose`

### 1.2 组描述大量缺失

6 个命令组没有 help 文本（传入 `help=None`）：

| 组 | help 参数 |
|---|----------|
| `review` | `None` |
| `merge` | `None` |
| `bookmark` | `None` |
| `following` | `None` |
| `followers` | `None` |
| `sync` | `None` |
| `maintainer` | `None` |

运行 `peerpedia --help` 时，这些组要么不显示描述，要么显示 `None`。

### 1.3 `?Mother` 命令

命令名为 `?Mother`，以 `?` 开头。这在 shell 中是一个 glob 通配符，会导致意外行为：

```bash
peerpedia ?Mother   # shell 将其扩展为当前目录中匹配 ?Mother 的文件
peerpedia '?Mother'  # 需要引号
peerpedia \?Mother   # 或者转义
```

这是一个复活节彩蛋/帮助命令，但命名方式会让用户困惑。

### 1.4 位置参数命名不一致

| 命令 | 参数名 | 含义 |
|------|--------|------|
| `article show` | `id` | 文章 ID |
| `article edit` | `id` | 文章 ID |
| `review submit` | `article_id` | 文章 ID |
| `maintainer add` | `article_id` | 文章 ID |
| `fork` | `article_id` | 文章 ID |

同一个概念用了两个不同的参数名（`id` vs `article_id`），这影响 `--help` 输出的一致性和用户的理解。

---

## 2. 帮助文档质量 — 3/10

### 2.1 参数帮助文本过于简短

| 参数 | 当前 help 文本 | 问题 |
|------|---------------|------|
| `article create --format` | `"Source format"` | 没有列出可选值（markdown/typst） |
| `article create --no-editor` | `"Create empty article without opening editor"` | 没有解释结果状态（空草稿） |
| `article publish --scores` | `"Self-review scores, e.g. …"` | 与 `review submit --scores` 描述不一致 |

### 2.2 帮助文本不一致

同一个概念在不同命令中有不同的措辞：

- `article publish --scores`：`"Self-review scores"`
- `review submit --scores`：`"Five-dim scores"`

- `merge propose --target`：`"Original article ID to merge into"`
- `merge accept --target`：`"Target article ID"`

- `article show id` metavar：`"Article ID (or prefix)"`
- `maintainer add article_id` metavar：`"Article ID"`（无前缀提示）

### 2.3 错误的默认值声明

`compile --format` 帮助文本说 `"(default: pdf)"`，但 argparse 中**没有设置** `default` 参数。编译器函数内部可能回退到 PDF，但 argparse 帮助文本具有误导性。

### 2.4 缺少命令概览

`peerpedia --help` 只列出命令名称和简短描述。没有：
- 使用示例（examples section）
- 典型工作流（"先 register → 再 create → 然后 publish"）
- 常见问题

`?Mother` 命令包含了一个详细的指南，但它是一个隐藏的复活节彩蛋，用户不会去输入。

---

## 3. 错误处理体验 — 3/10

### 3.1 `_with_db` 装饰器暴露完整 traceback

```python
except Exception as e:
    import traceback
    traceback.print_exc()
    _die(str(e))
```

当任何命令失败时，用户会看到：

```
Traceback (most recent call last):
  File "…/cli/helpers.py", line XX, in wrapper
    return func(db, args)
  File "…/cli/handlers/articles.py", line XX, in _cmd_article_edit
    …
ValueError: Repo has no commits

✗ Repo has no commits
```

普通用户看到 Python traceback 会认为程序崩溃了。traceback 应该只在 `--debug` 模式下显示。

### 3.2 错误消息质量参差不齐

**好的：**
- `"No user specified. Register first:\n  peerpedia account register --name <your-name>"` — 具体、可操作

**差的：**
- `"User '{user_id}' not found — DB inconsistency."` — 告诉用户"数据库不一致"，但这不是用户能修复的
- `"Repo has no commits"` — 技术细节，对用户无意义
- `"DB has reviews but no reviews/ directory on disk"` — 内部实现细节泄露

### 3.3 重复的错误输出

REPL 中的错误处理：argparse 向 stderr 打印错误，然后 REPL 的 `except Exception` 捕获 `SystemExit(2)` 并用字符串重写异常。结果是：
1. argparse 的错误消息（进入被抑制的 stderr）
2. REPL 显示 `"✗ unrecognized arguments: …"`（可能为空）

### 3.4 非交互式使用缺少 `--force`/`--yes`

`article delete` 强制使用交互式 `[y/N]` 确认，没有 `--force` 或 `--yes` 标志。脚本化/自动化使用不可能。

---

## 4. 成功反馈一致性 — 5/10

### 4.1 某些操作静默成功

`_cmd_article_create` 在文本模式下**没有**成功确认消息。它调用 `_resolve_and_display_article()` 渲染文章面板，但用户看不出文章是新创建的还是只是显示。没有 `_ok("Created …")` 调用。

对比 `_cmd_article_edit`，后者同时调用了 `_ok()` **和** `_resolve_and_display_article()`（双重确认）。

### 4.2 `_try_sync()` 调用不一致

| 会调用 `_try_sync()` | 不会调用 `_try_sync()` |
|---------------------|----------------------|
| `article create`, `edit`, `publish` | **`article delete`** |
| `fork`, `merge accept` | **`merge propose`** |
| `bookmark remove` | **`bookmark add`** |
| `follow`, `unfollow` | **`maintainer add/remove`** |
| `review submit` | |

用户执行 `article delete` 后，删除操作不会自动推送到 peer server。用户可能以为删除已经同步了。

### 4.3 `following`/`followers` 只显示计数

```
✓ Following 3 user(s)
```

文本模式下只输出计数，没有列出具体用户。`users` 变量被获取但完全丢弃。JSON 模式正确返回完整列表。

---

## 5. 输出格式 — 6/10

### 5.1 做得好的

- Rich 库提供彩色输出、面板、表格
- `_json_out()` 提供机器可读的 JSON 模式
- 5 维评分用星星（★★★★☆）直观展示
- 文章/用户显示用 Panel 布局，信息层次清晰

### 5.2 `--json` 标志在部分命令中无效

以下命令解析 `--json`（通过 `_add_common` 添加）但处理函数从不读取：

| 命令 | 行为 |
|------|------|
| `article delete` | 忽略，永远输出文本 |
| `sync status` | 忽略 |
| `sync push` | 忽略 |
| `sync pull` | 忽略 |
| `compile` | 忽略 |
| `server start` | 忽略 |
| `?Mother` | 忽略 |

用户传递 `--json` 期望机器可读输出，得到的是 Rich 格式化的文本。

### 5.3 小文案不一致

- `_stars()` 在无分数时返回 `"no score"`（单数）
- `display_article()` 在无分数时显示 `"no scores"`（复数）

---

## 6. REPL 体验 — 5/10

### 6.1 做得好的

- 无参数启动进入 REPL 而非报错
- Sticky user（`:user alice`）减少重复输入
- `Shift+Enter` 提交，`Enter` 换行（支持多行输入）
- `:help` 显示组织良好的命令面板
- 定时自动发布沉淀完成的文章

### 6.2 问题

- **无历史记录持久化** — REPL 重启后历史丢失
- **无 tab 补全** — 虽然有 `COMMANDS` 和 `FLAGS` 列表，但没有连接到 prompt_toolkit 的补全器（代码中定义了列表但未使用）
- **无 `:cd` / `:pwd` 导航** — REPL 是一个封闭环境
- **启动 banner 过于简短** — `"PeerPedia REPL\nType :help for commands, :quit to exit."` — 没有提示当前登录用户、文章数量

---

## 7. 命令发现性 — 2/10

### 7.1 功能隐藏在代码中

用户无法通过命令行发现以下功能：
- 评分系统的 5 个维度具体是什么（`origin=,rigor=,reprod=,mech=,sig=`）
- 文章 ID 支持前缀匹配（帮助文本中有时提到有时没提到）
- `PEERPEDIA_SERVER` 环境变量的存在和用途（只在 sync 帮助中提及）
- 配置文件的位置（`~/.peerpedia/`）

### 7.2 工作流不透明

新用户的困惑点：
1. 注册后不知道下一步该做什么
2. 创建文章后不知道怎么发布
3. 不知道什么时候需要配置 peer server
4. 不理解沉淀池（sedimentation）机制

`?Mother` 命令包含所有这些信息，但它叫 `?Mother`—— 用户不知道去输入它。

---

## 8. 交互确认与安全 — 4/10

### 8.1 确认不一致

| 操作 | 有确认？ |
|------|---------|
| `article delete` | ✅ `[y/N]` 提示 |
| `merge accept` | ❌ 无确认，直接执行 |
| `article publish` | ❌ 无确认 |
| `follow`/`unfollow` | ❌ 无确认 |

`merge accept` 是一个可能有副作用的合并操作，但没有确认提示。

### 8.2 潜在的数据丢失风险

- `article delete` 没有 `--dry-run` 预览模式
- 合并冲突时只显示 `⚠ Conflict`，没有交互式解决
- 没有文章锁定提示（如果另一个用户正在编辑）

---

## 缺失功能清单

### P0 — 阻塞用户体验
1. **无 `--force`/`--yes` 标志** — 无法在脚本中使用 `article delete`
2. **`following`/`followers` 不显示用户列表** — 只能看到计数
3. **`article create` 无成功提示** — 用户不知道自己创建成功

### P1 — 严重损害体验
4. **无 `--debug` 模式** — 错误总是显示 traceback
5. **7 个命令 `--json` 被静默忽略** — 用户以为输出是 JSON
6. **6 个命令组缺少帮助描述** — `peerpedia --help` 不完整
7. **`?Mother` 命令名问题** — shell glob 冲突
8. **无 tab 补全实现** — 列表已定义但未连入 prompt_toolkit
9. **无新用户引导** — 初次使用不知道从哪里开始
10. **`_with_db` 暴露 traceback** — 应该只在 debug 模式下显示

### P2 — 改善体验
11. **`_try_sync()` 调用不一致** — 半数的状态变更操作不同步
12. **无命令别名** — 无法用 `articles` 代替 `article` 等
13. **无历史记录持久化** — REPL 重启丢失
14. **位置参数命名不统一** — `id` vs `article_id`
15. **帮助文本不一致** — 同一个概念多种措辞
16. **无 `--dry-run` 支持** — 无法预览操作效果
17. **REPL 启动 banner 信息量不足** — 不显示当前用户/文章数
18. **`--scores` 帮助文本不一致** — "Self-review" vs "Five-dim"
19. **`PAGER` 环境变量解析脆弱** — 使用 `.split()` 而非 `shlex.split()`
20. **`article delete --json` 被忽略** — 文档声称支持但代码没有

---

## 建议修复优先级

### 批处理 1：立即修复（用户可见的 bug）
- 修复 `article create` 缺失成功提示
- 修复 `following`/`followers` 不显示用户列表
- 为 `article delete` 添加 `--force` 标志
- 修复 7 个命令中 `--json` 被忽略的问题

### 批处理 2：错误处理体验
- 添加 `--debug` 标志，traceback 只在 debug 模式下显示
- 重写面向实现细节的错误消息（"DB inconsistency" → "Something went wrong. Try again or run peerpedia doctor."）
- 统一错误输出：CLI handler 使用 `_die()`、sync loop 使用 `[warning]⚠`、auto-sync 使用 `[dim]⚠`—— 需要明确的严重级别分层

### 批处理 3：命令结构清理
- 统一命令分组策略（全扁平或全嵌套）
- 为所有命令组添加帮助描述
- 重命名 `?Mother`（如 `guide` 或 `help` 子命令）
- 统一位置参数命名（全部用 `article_id`）
- 统一 `--scores`/`--target` 等帮助文本

### 批处理 4：新用户引导
- 首次运行 `peerpedia` 时显示快速入门（而非直接进 REPL 或报错）
- 添加 `peerpedia guide` 命令替代 `?Mother`
- 在每个命令的 `--help` 中添加至少一个示例
- REPL 启动时显示当前用户状态和最近文章

---

## GSTACK REVIEW REPORT

| Runs | Status | Findings |
|------|--------|----------|
| 1 | **DONE_WITH_CONCERNS** | 8 维度评分，20 项缺失功能，4 个优先批次 |

### 评分卡

| 维度 | 评分 | 关键问题 |
|------|------|----------|
| 命令结构与分组 | 4/10 | 不一致的顶层/子命令分组，6 个组无描述，`?Mother` 命名冲突 |
| 帮助文档质量 | 3/10 | 简短的参数帮助，不一致的措辞，无使用示例 |
| 错误处理体验 | 3/10 | 向用户暴露 traceback，面向实现细节的错误消息 |
| 成功反馈一致性 | 5/10 | `article create` 无确认，`_try_sync` 调用不一致 |
| REPL 体验 | 5/10 | 无 tab 补全、无历史持久化、banner 信息不足 |
| 命令发现性 | 2/10 | 功能隐藏在代码中，无新用户引导 |
| 输出格式 | 6/10 | Rich 格式化好，但 7 个命令 `--json` 被静默忽略 |
| 交互确认与安全 | 4/10 | 删除有确认但合并没有，无可脚本化标志 |

### VERDICT

**综合评分 4/10。** CLI 的核心功能（CRUD 文章、评分、同步）在工作，但用户界面粗糙得像内部工具。最严重的问题是：向用户暴露 Python traceback、`--json` 标志在 7 个命令中被静默忽略、错误消息充满实现细节、新用户不知道从哪里开始。后端的评分/同步系统设计精良，但 CLI 的对用户界面投资严重不足。

NO UNRESOLVED DECISIONS
