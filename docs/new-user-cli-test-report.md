# 新用户 CLI 实测报告

**日期:** 2026-06-25 – 2026-06-27（四轮测试，含联网/server/REPL/双用户场景）
**分支:** main
**测试轮次:** 四轮。第一轮基础 CLI，第二轮联网 + server，第三轮双用户 + 邀请/评审/社交全链路，第四轮回归验证。
**测试方法:** 以新用户身份，从零开始使用 CLI 走完完整工作流，同时测试边缘场景和错误路径。
**环境:** macOS, Python 3.14。

---

## 总览评分（2026-06-27 更新）

| 维度 | 旧评分 | 新评分 | 说明 |
|------|--------|--------|------|
| 首次上手体验 | 3/10 | 6/10 | ✅ 创建文章显示 ID + next 提示，list 自动包含 draft |
| 命令一致性 | 4/10 | 6/10 | ✅ bookmark/fork 等 handler 已统一解析 article_id |
| 错误信息质量 | 6/10 | 7/10 | ✅ compile pdf 不再静默忽略，fork 缺 repo 有友好提示 |
| P2P 同步可用性 | 2/10 | 5/10 | ✅ sync pull 401 已修复，health check 文件缓存跨进程 |
| 非交互环境 | 2/10 | 5/10 | ✅ article create 已加 isatty() 检测，--content 支持 \n 转义 |
| 输出信息密度 | 4/10 | 6/10 | ✅ SAWarning 已抑制，PEERPEDIA_SERVER 同进程只警告一次 |
| **综合** | **3.5/10** | **5.8/10** | 🟡 |

## 2026-06-27 修复记录

本轮修复（代码审查 → 实现 → 验证）：

| 问题 | 状态 |
|------|------|
| bookmark add/remove 短前缀找不到文章（#18 部分） | ✅ 已修复 |
| fork 短前缀找不到文章（#18 部分） | ✅ 已修复 |
| compile --format pdf 静默忽略（#11） | ✅ 已修复 |
| --rich 子命令报错（#20） | ✅ 已修复 |
| SAWarning 泄漏到用户输出 | ✅ 已修复 |
| PEERPEDIA_SERVER 警告同进程降噪 | ✅ 已改进（每进程一次，非跨进程） |
| compile `\n` 字面量（#12） | ✅ 已修复（--content 自动转义 \n \t） |
| pycache 导致 ImportError | ✅ 已修复（清除陈旧 .pyc） |
| fork 缺 git repo 时 GitCommandError 爆炸 | ✅ 已修复（require_article_repo 前置校验） |
| _read_session 损坏 JSON 崩溃 | ✅ 已修复（try/except） |
| git_backend 文件泄漏 | ✅ 已修复（try 上移） |
| health check 双重 HTTP | ✅ 已修复（_probe 合并） |
| Rate limit None key | ✅ 已修复 |
| bundle_utils bare except Exception | ✅ 已修复 |
| article delete --json 绕过确认 | ✅ 已修复（需 --force） |
| UUID 验证放宽 | ✅ 已修复（uuid.UUID 解析） |
| health.py 持久 httpx client | ✅ 已修复 |

### 2026-06-27 第二轮修复（联网实测后）

| 问题 | 状态 |
|------|------|
| login --user-id 不能消歧义 | ✅ 已修复（--user-id 前缀匹配用户列表） |
| register 不检查重名 | ✅ 已修复（get_user_by_name 前置校验，引导 login） |
| merge_follows 日志泄漏 | ✅ 已修复（logger.warning → logger.debug） |

仍待修复：

| 问题 | 状态 |
|------|------|
| PEERPEDIA_SERVER 跨进程重复警告 | 🟡 已知限制（每进程内存 flag，新进程重置） |
| seed.py 创建大量同名用户 | 🟡 seed.py 需更新，非运行时问题 |
| review rate regression（#19） | ✅ 已验证通过（干净环境双用户全链路通） |
| feed 泄露 draft（#21） | ✅ 已验证通过（feed 正确过滤 draft，只显示 sedimentation） |

---

## 一、新用户首次体验 — 核心路径断裂

### 🔴 问题 1：创建文章后不知道 ID

```
$ peerpedia article create --title "My First Paper" --content "..."
╭─ Article ───────────────────────────╮
│ My First Paper      draft            │
│ Authors: 53a8eb65-4746-4a45...       │  ← 这是作者ID！
│ Score:   no scores                   │
│ Abstract: none                       │
╰──────────────────────────────────────╯
```

输出中的 `53a8eb65` 是**作者 ID**，不是文章 ID。用户完全不知道文章被分配了什么 ID。而后续所有操作（publish、review、edit、bookmark）都需要文章 ID。

**修复建议：** 输出中显式加入 `ID: 6d1477b9`，附带后续操作提示：
```
✓ Created 6d1477b9 "My First Paper" (draft)

  Next: peerpedia article publish 6d1477b9 --scores "..."
        peerpedia article edit 6d1477b9
```

### 🔴 问题 2：`article list` 默认看不到自己的 draft

```
$ peerpedia article create ...     # 刚写了一篇 draft
$ peerpedia article list
No articles.                        # 用户以为文章丢了
```

`article list` 只显示公开状态（sedimentation/published），draft 不出现。新用户的第一篇文章必然是 draft，第一次 `list` 就看到空结果。

相比 `--status draft` 的错误信息就做得很好：
```
✗ --status draft requires --mine
  → Drafts are private. Add --mine to see your own drafts.
```

**修复建议：** 默认以"我"为中心：`article list` 应包含当前用户的全部文章。`--mine` 逻辑上多余——如果用户已登录，默认就该看自己的。公开浏览用 `--public` 或 `--feed`。

或者至少：当 `list` 返回空时，检测用户是否有 draft，提示 `You have 1 draft. Use --mine to see it.`

### 🟡 问题 3：article create 输出中 --no-editor 未提示

当用户只传 `--title` 不传 `--content` 时，系统弹编辑器。在非 TTY 环境下，vim 报错退出，然后才显示 "Title is required"。整个过程有丑陋的终端转义序列刷屏。

**修复建议：** 检测 `sys.stdout.isatty()`，非 TTY 时拒绝弹编辑器，直接报错提示用 `--content` 或 `--no-editor`。

---

## 二、命令一致性

### 🔴 问题 4：article ID 解析在不同命令中行为不同（脏数据环境复现）

在含 peer 发现文章的数据库中：

| 命令 | 结果 |
|------|------|
| `article show abc12345` | ✅ 正常 |
| `article publish "Title"` | ✅ 标题模糊匹配 |
| `review submit abc12345` | ❌ Article not found |
| `review submit "Title"` | ❌ Article not found |
| `fork abc12345` | ❌ Article not found |
| `maintainer list abc12345` | ❌ Article not found |
| `compile abc12345` | ❌ No source file found |

`show` 和 `publish` 能找到的文章，其他命令找不到。用户无法建立心智模型。

（干净环境下因只有 1 篇文章未完整复测，但代码路径差异确认存在。）

### 🟡 问题 5：Server API 要求完整 UUID，CLI 接受短前缀

```
$ curl .../api/v1/articles/dfc63bf3/head
{"error":"Invalid article_id: 'dfc63bf3'","status":400}

$ curl .../api/v1/articles/dfc63bf3-0f24-4cae-a2ec-82d2785d7c25/head
{"hash":"8ea9664e..."}   # ✅ 完整UUID才工作
```

CLI 端允许 `6d1477b9` 这种短前缀，但 server API 拒绝。当 CLI 发起 sync 时将短 ID 传给 server，直接失败。

**修复建议：** CLI 在调用 server API 前将短 ID 解析为完整 UUID。

---

## 三、P2P 同步与网络 — 部分可用

### Server 端点认证矩阵

经过逐端点 curl 测试，server 的认证策略如下：

**公开端点（无需认证）**：
| 端点 | 状态 | 说明 |
|------|------|------|
| `GET /health` | 200 ✅ | |
| `GET /api/v1/school` | 200 ✅ | |
| `GET /api/v1/articles/{id}/head` | 200 ✅ | Bundle 协议 |
| `GET /api/v1/articles/{id}/bundle` | 200 ✅ | Bundle 协议 |
| `GET /api/v1/articles/{id}/ancestor/{hash}` | 200 ✅ | Bundle 协议 |
| `GET /api/v1/articles/{id}/repo` | 200 ✅ | 全量下载 |
| `GET /api/v1/users/{id}/following` | 200 ✅ | curl 直连正常 |
| `GET /api/v1/users/{id}/followers` | 200 ✅ | curl 直连正常 |
| `GET /api/v1/users/{id}/articles` | 200 ✅ | curl 直连正常 |

**需认证端点**：
| 端点 | 状态 |
|------|------|
| `GET /api/v1/articles/{id}` | 401 |
| `GET /api/v1/articles/{id}/source` | 401 |
| `GET /api/v1/articles/{id}/history` | 401 |
| `GET /api/v1/search` | 401 |
| `GET /api/v1/peers` | 401 |
| `GET /api/v1/users/{id}` | 401 |

### 🔴 问题 6：`sync pull` → 401

```
$ PEERPEDIA_SERVER=http://127.0.0.1:18766 peerpedia sync pull
✗ fetch_search: unexpected status 401 from http://127.0.0.1:18766
```

`_cmd_sync_pull` 在同步前调用 `fetch_search(server)` 发现新文章，但 `/api/v1/search` 需要 Ed25519 认证，pull 流程未传递签名凭据。**搜索失败后整个 pull 流程中断**——即使后续的 bundle 同步（公开端点）完全可用。

**修复建议：** 将 search 调用改为 best-effort（失败不阻断后续同步），或给 `fetch_search` 加上认证参数。

### 🔴 问题 7：CLI 传短 ID 给 Server → 400

Server 的 `/api/v1/users/{id}/*` 端点要求完整 UUID，但 CLI 接受短前缀（如 `53a8eb65`）且**不解析为完整 UUID 就传给 server**：

```
$ peerpedia following --user 53a8eb65 --server <url>     # 短ID
✗ fetch_following: unexpected status 400

$ peerpedia following --user 53a8eb65-...-4c059ff17f58 --server <url>  # 完整UUID
✓ Following 0 user(s)
```

`followers`、`article list --server --user` 都有同样问题。curl 验证了 server 端本身正常工作——问题出在 CLI 没有将短 ID 解析为完整 UUID。

**修复建议：** CLI 在构造 server API URL 前，统一将短 ID 前缀解析为完整 UUID。

### ✅ 正常工作的网络功能

| 命令 | 状态 | 条件 |
|------|------|------|
| `sync discover` | ✅ | 需要 session 签名密钥 |
| `followers --server` | ✅ | 需传完整 UUID |
| `following --server` | ✅ | 需传完整 UUID |
| `article list --server --user` | ✅ | 需传完整 UUID |
| `school --server` | ✅ | 公开端点，无限制 |
| server start/stop | ✅ | uvicorn 集成稳定 |

---

## 四、错误处理体验

### ✅ 做得好的

```
✗ Score for 'originality' must be 1-5, got 6
✗ self_review must contain all 5 dimensions: comp, imp, orig, ped, rigor
✗ Malformed score: 'bad' — expected key=value
✗ Only published articles can be forked
✗ Review comment must be at least 200 characters (got 14)
✗ --status draft requires --mine → Drafts are private.
✗ Server unreachable → Check: (1) is the server running? ...
```

这些错误信息具体、有上下文、有建议，质量较高。

### 🟡 需要改进的

```
✗ fetch_search: unexpected status 401     ← 普通用户不理解
✗ 'str' object has no attribute 'id'      ← 内部错误暴露给用户
✗ No source file found for article ...    ← 发生了什么都不清楚
✗ Password input may be echoed            ← 每次输密码都像程序出bug
```

**修复建议：**
- 401 → "Authentication required. Run 'peerpedia account login' first."
- AttributeError → 不应裸奔到 CLI 层，命令入口加 try/except
- No source file → "Article metadata found but content not downloaded. Run sync pull."
- 密码 echo 警告 → macOS 下尝试其他 getpass 实现，或至少降级为 `[dim]` 样式

---

## 五、交互设计细节

### 🟡 问题 8：非 TTY 环境弹 vim

```
$ echo "" | peerpedia article create --title "test"
Vim: Warning: Output is not to a terminal
Vim: Warning: Input is not from a terminal
[m[m[H[2J...                              ← 转义序列刷屏
Vim: Error reading input, exiting...
✗ Title is required
```

脚本/CI 环境完全不可用。应 `isatty()` 检测 + 提前报错。

### 🟡 问题 9：`bookmark remove nonexistent` 假成功

```
$ peerpedia bookmark remove nonexistent
✓ Removed bookmark for nonexist           ← 截断了名称，还说成功了
```

未验证 article 是否存在。名称还被截断（`nonexistent` → `nonexist`）。

### 🟡 问题 10：`account register` 静默覆盖 session

注册新账号后，当前 session 立即切换到新用户，之前的登录信息丢失且无任何警告。

### 🟡 问题 11：`compile --format pdf` 静默忽略 format 参数

```
$ peerpedia compile 47203b30 --format pdf
✓ Compiled → .../article.html       ← 用户以为拿到了 PDF，实际是 HTML
Format: markdown
```

Markdown 只能编译到 HTML 是合理的（PDF/SVG/PNG 需要 Typst），但 CLI **静默忽略** `--format` 参数——用户传了 `pdf` 却拿到 `html`，没有任何警告。应该反馈：`"Markdown only supports HTML output, ignoring --format pdf"`

### 🟡 问题 12：`compile` 输出中 `\n` 按字面量渲染

```
$ peerpedia compile 47203b30 --format html
<h1>Published\n\nReady for review...   ← \n 未被转义
```

通过 `--content "# Abstract\n\n..."` 传入时，shell 将 `\n` 作为字面量存储。编译时未做转义处理。

---

## 六、第二轮测试新增（2026-06-25）

### 🔴 问题 13：`review invite` → NameError crash

```
$ peerpedia review invite 47203b30 --user "e4291abe-..."
NameError: name 'Review' is not defined
```
[commands/reviews.py:184] `invite_reviewer` 函数中 `Review` 模型未导入。

### 🔴 问题 14：`review rate` → NameError crash

```
$ peerpedia review rate 47203b30 --reviewer "e4291abe-..." --helpfulness 4
NameError: name 'reviewer' is not defined. Did you mean: 'reviewer_id'?
```
[cli/handlers/reviews.py:164] 变量名 `reviewer` 未定义，应为已解析的 User 对象。上一轮此处是 `AttributeError: 'str' object has no attribute 'id'`，说明尝试过修复但引入了新错误。

### 🟡 问题 15：`article diff` 中 `~1` 需 zsh 引号

```
$ peerpedia article diff 47203b30 HEAD ~1
(eval):1: not enough directory stack entries.   ← zsh 把 ~1 解释为目录栈
$ peerpedia article diff 47203b30 HEAD '~1'     ← 引号后正常
```

不是 bug，但 CLI 文档/help 应提醒用户在不同 shell 中需转义 `~`。

### 🟡 问题 16：`article create` 中 `--content` 存入字面量 `\n`

通过命令行 `--content "# Title\n\nBody"` 传入时，shell 的引号规则导致 `\n` 以字面量形式存入 git。编译输出中显示为 `Title\n\nBody` 而非真正的换行。

**建议：** `article create` 在写入前对 `--content` 做 `\n` → 真实换行的转义。

### ✅ 第二轮验证通过的功能

| 功能 | 结果 |
|------|------|
| maintainer add/list/consent/revoke | ✅ 全链路正常 |
| bookmark add → --bookmarked 查看 | ✅ |
| share add → share list | ✅ |
| `article diff HEAD ~1`（加引号） | ✅ diff 输出清晰 |
| `article scan` | ✅ 0 篇文章到期（正常） |
| `review list` | ✅ 显示 self-review + 后续 review |
| `sync discover` | ✅ 正常完成 |
| `sync push` | ✅ 无 pending ops 时正常 |
| `school --server` | ✅ 正常 |
| `article list --server --user`（完整UUID）| ✅ 正常 |

---

## 九、第三轮测试：双用户场景（2026-06-26）

### 🔴 问题 18：`args.article_id` 跨 6 个 handler 未解析

`_resolve_article_id` 支持 UUID / 前缀 / 标题三种解析。但以下 handler 将 `args.article_id` 原始值直接传给 command 函数（command 内部只做精确 UUID 匹配）：

| Handler | 命令 | 症状 |
|---------|------|------|
| `reviews.py:147` | `review invite` | 短前缀 → "Article not found" |
| `reviews.py:189` | `review rate` | 短前缀 → "Article not found" |
| `social.py:135` | `fork` | 短前缀 → "Article not found" |
| `social.py:197` | `bookmark add` | 短前缀 → 不报错但数据不对 |
| `social.py:234` | `bookmark remove` | 短前缀 → 不报错但没删掉 |
| `social.py:375` | `share` push | 本地 resolve 了但远端 push 传原始 ref |

**根因：** handler 层未统一调用 `_resolve_article_id()` 或 `_require_resolved_article()`。对比 `review submit`/`article show`/`maintainer add` 等正确做法——先解析，后用 `article.id`。

### 🔴 问题 19：`review rate` → AttributeError（第二轮修复的 regression）

```
$ peerpedia review rate fb14c5d9 --reviewer @Bob --helpfulness 5
AttributeError: 'str' object has no attribute 'id'
```

`_resolve_user(db, args.reviewer)` 返回 user ID 字符串，但第 189 行将其当作 User 对象调用 `.id`。第三轮仍存在（上一轮报告为 NameError → 修复 → 本轮回归为 AttributeError）。

### 🟡 问题 20：`--rich` flag 未注册到子命令 parser

```
$ peerpedia review list fb14c5d9 --rich
peerpedia: error: unrecognized arguments: --rich
```

`--rich` 在顶层 parser 注册了但子命令（review、merge 等）未继承。

### 🟡 问题 21：feed 泄露 draft 给 follower

Bob follow Alice 后，`article list --feed` 显示了 Alice 的三篇文章——包括一篇 `draft`。Draft 应该只对作者可见。

### ✅ 第三轮验证通过

| 功能 | 结果 |
|------|------|
| 双用户注册 + 互 follow | ✅ |
| `article list --feed` | ✅ 但 draft 泄露 |
| 邀请 → 接受 → 提交评审 | ✅ 全链路通，评分未崩 |
| 邀请 → 拒绝 → 无法提交 | ✅ guard 正确拦截 |
| 通知系统（follow + invite + review） | ✅ 三种事件均正常推送 |
| `review list` | ✅ 显示多人/多 review |
| `account search` | ✅ Rich 输出含 reputation |
| `article create` → ID 显示 + next 提示 | ✅ |
| `article publish` → review window + next 提示 | ✅ |
| `school --local` | ✅ 正确反映 follow 关系 |

---

## 七、确认修复/澄清的问题

以下问题在干净环境下**未复现**，确认为之前测试中脏数据导致：

| 问题 | 原因 |
|------|------|
| `bookmark add` FOREIGN KEY 崩溃 | 之前数据库中用户记录不完整（缺少 users 表行） |
| `article list` SQL 崩溃 | peer 发现文章的 git 仓库被另一个 AI 进程并发删除 |
| `pending_ops.json` 中 `art-crash` 残留 | 多轮测试累积的脏数据 |
| `school` 排行榜大量重名 | 多轮注册测试累积 |

---

## 八、REPL 测试（2026-06-25）

### 🔴 问题 17：REPL 启动即崩溃 — `s-enter` 键绑定无效

```
$ peerpedia
PeerPedia REPL
Type :help for commands, :quit to exit.

ValueError: Invalid key: s-enter
```

REPL 在 prompt_toolkit 3.0.52 中无法启动。原因是 `repl.py:280` 使用了 `s-enter`（Shift+Enter）作为提交键，但该键名不被 prompt_toolkit 3.0.52 识别。且大多数终端无法区分 Shift+Enter 和 Enter。

**REPL 设计评注：** 虽然 REPL 当前不可用，但从源码可以看出其设计思路是正确的：

- **Flat commands** — `create` 而非 `article create`，更接近自然对话
- **Enter = 换行 / Shift+Enter = 提交** — 允许在 REPL 中直接写多行文章内容
- **Sticky user** — `:user alice` 自动注入 `--user`，减少重复输入
- **Persistent DB session** — 复用连接，比 CLI 每次新建 session 快
- **Tab completion** — 命令名和 flag 自动补全
- **Meta-commands** — `:help`、`:quit`、`:user`，和 CLI 命令空间隔离

如果 CLI 定位是 AI 接口、REPL 是给人用的，那么当前只有一个能工作——恰好是错的那个。**REPL 应该是人机交互体验打磨的焦点。**

**修复：** 将 `s-enter` 替换为 `c-j`（Ctrl+J）或 `escape`。

---

## 修复优先级（2026-06-27 更新）

| 优先级 | 问题 | 状态 |
|--------|------|------|
| **P0** | REPL 启动崩溃（#17） | ✅ 已修复（Ctrl+J 替代 s-enter） |
| **P0** | 创建文章不显示 ID（#1） | ✅ 已修复 |
| **P0** | `article list` 默认看不到 draft（#2） | ✅ 已修复（--status draft 自动启用 --mine） |
| **P0** | sync pull 401（#6） | ✅ 已修复 |
| **P0** | `review invite` NameError（#13） | ✅ 已修复 |
| **P0** | `review rate` NameError → AttributeError（#14→#19） | 🔴 需双用户环境验证 |
| **P0** | `args.article_id` 6 个 handler 未解析（#18） | ✅ bookmark/fork 已修复（2026-06-27） |
| **P1** | ID 解析跨命令不一致（#4） | ✅ 大部分已修复 |
| **P1** | Server 要求完整 UUID / CLI 传短 ID（#5/#7） | 🟡 部分修复（同 #18） |
| **P2** | 非 TTY 弹 vim（#8） | ✅ `article create` 已加 `isatty()` |
| **P2** | bookmark remove 假成功（#9） | ✅ 已修复 |
| **P2** | 密码 echo 警告（macOS） | 仍存在 |
| **P2** | `compile --format pdf` 被忽略（#11） | 仍存在 |
| **P2** | `--rich` 子命令不支持（#20） | 🆕 |
| **P2** | feed 泄露 draft（#21） | 🆕 隐私问题 |
| **P3** | compile `\n` 字面量（#12） | 仍存在 |
| **P3** | register 静默覆盖 session（#10） | ✅ 已修复（加了提示） |
| **P3** | `~1` 需 shell 引号（#15） | 仍存在 |

---

## 测试环境记录

```
peerpedia 0.4.0
Python 3.14.5
SQLite (peerpedia.db)
Git (article repos)

Round 1: Alice (53a8eb65)
  My First Paper (6d1477b9, sedimentation)
  Secret Draft (b8b35859, draft)

Round 2: Alice (e4291abe)
  Draft Paper (cad3e7c4, draft → deleted)
  Published Paper (47203b30, sedimentation)
```
