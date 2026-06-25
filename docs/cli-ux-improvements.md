# CLI UX 改进建议

**日期:** 2026-06-25
**类型:** 体验打磨建议（非 bug）
**原则:** 单行改动级别，不动架构，提升留存。

---

## 一、冷启动引导

### 1. 无参数默认输出精简 Dashboard

当前 `peerpedia` 无参数输出 30 行的 `--help`，新用户不知所措。`?Mother` 是好的引导页但需要用户主动发现。

**建议：** 检测到已登录用户时，输出精简状态面板：

```
PeerPedia — peer review from the terminal.

Currently: Alice (e4291abe)
  Drafts:      2
  In review:   1
  Published:   0
  Feed:        0 new

Get started:
  peerpedia article create --title "My Paper"
  peerpedia article list --mine
  peerpedia ?Mother                   ← full guide
```

### 2. `?Mother` 引导闭环

`?Mother` 末尾写的是 "In the future, I'll be able to answer questions"。把这条兑现——至少做命令速查。

```
╭─ ?Mother — PeerPedia Guide ───────────────────╮
│ ...(current content)...                        │
│                                                │
│ Quick reference:                               │
│   article create    Write a new paper          │
│   article publish   Submit for peer review     │
│   review submit     Review someone's paper     │
│   school            Discover users to follow   │
│   sync push/pull    Sync with peers            │
│                                                │
│ Type any command with --help for details.      │
╰────────────────────────────────────────────────╯
```

---

## 二、上下文连续感 — 每个操作给出下一步

### 3. `article create` → 提示后续操作

```
✓ Created 47203b30 "My First Paper" (draft)

  Next: peerpedia article publish 47203b30 --scores "..."
        peerpedia article edit 47203b30
```

### 4. `article publish` → 告知 review 窗口和到期时间

```
✓ Published to sedimentation pool.

  Review window: 7 days. Auto-publishes after 2026-07-02.
  Scores: orig=4 rig=4 comp=3 ped=3 imp=4

  Next: peerpedia share add 47203b30
        peerpedia review invite 47203b30 --user <id>
```

### 5. `review submit` → 提示不可编辑

```
✓ Review submitted. Reviews cannot be edited — submit another to amend.

  Next: peerpedia review list 47203b30
```

---

## 三、空状态应该是引导，不是沉默

### 6. `article list --feed` 空 → 引导去发现

当前返回 `No articles.`。

```
Your feed is empty — you're not following anyone yet.

  peerpedia school              ← discover users
  peerpedia follow @alice       ← follow someone
  peerpedia article list --feed ← see their articles

Set PEERPEDIA_SERVER to discover users on the P2P network.
```

### 7. `school` 空 → 引导去 peer 网络

```
No users found locally.

  Set PEERPEDIA_SERVER to connect to the peer network:
    export PEERPEDIA_SERVER=https://peer.example.com
  Then: peerpedia school --server $PEERPEDIA_SERVER
```

### 8. `following`/`followers` 空 → 引导去 follow

```
Not following anyone yet.

  peerpedia school   ← find users to follow
  peerpedia follow @username
```

---

## 四、反馈透明度

### 9. 不可逆操作加确认

当前 `article delete` 有 y/N 确认，但 `publish`、`review submit`、`merge accept` 没有。建议统一加确认（可通过 `--yes` 跳过）：

```
Publish "My First Paper" to the sedimentation pool?
This starts a 7-day public review period and cannot be undone.
  [y/N]
```

### 10. 幂等操作明确反馈

```
$ peerpedia bookmark add 47203b30
✓ Bookmarked (already saved).

$ peerpedia follow @alice
✓ Already following @alice.
```

### 11. `article list` 显示总数和状态分布

```
╭─ Article ── ... ──╮
...                  ...
╰────────────────────╯
[dim]3 articles: 1 draft, 1 in review, 1 published[/]
```

### 12. `compile --format pdf` 不能静默忽略

Markdown 只能输出 HTML 是合理限制，但不能沉默：

```
⚠ Markdown articles only support HTML output. Use Typst for PDF/SVG/PNG.
✓ Compiled → article.html
```

---

## 五、评审体验

### 13. 200 字最低限制给出写作引导

当前：
```
✗ Review comment must be at least 200 characters (got 14)
```

建议：
```
✗ Review too short: 14/200 characters.

  A good review addresses:
  • What did the author do well?
  • What could be improved?
  • Any missing references or alternative approaches?

  Current: 186 characters remaining.
```

### 14. review 提交后提示不可编辑

```
✓ Review submitted. Reviews are permanent. Submit a new review to amend or add thoughts.
```

---

## 六、提醒降噪

### 15. `No PEERPEDIA_SERVER set` 降低频率

当前几乎所有命令都打印这条 warning。本地模式是设计选择，不应读起来像错误。

**建议：** 首条命令显示一次 `[dim]` 提示，之后静默积累 pending ops。`sync push` 时统合汇报。

### 16. 密码 echo 警告降级

macOS 下 `GetPassWarning` 每次注册/登录都弹。尝试 `termios` 方案，或至少降级显示：

```
[dim]Password input may be visible in this terminal.[/]
```

---

## 七、小细节

### 17. `school` 无 server 时自动 fallback 到 `--local`

```
$ peerpedia school
[dim]No server configured — showing local results.[/]
  School — Top Users by Followers
  ...
```

### 18. `article diff` 的 `~N` 路径加 shell 提示

```
$ peerpedia article diff 47203b30 HEAD ~1   ← zsh 报错
(eval):1: not enough directory stack entries.

  Tip: In zsh, quote the ref: peerpedia article diff 47203b30 HEAD '~1'
```

在 `article diff --help` 的 EXAMPLES 中展示多种 shell 的正确写法。

### 19. 紧凑列表模式

大 panel 是好的默认——信息完整、可读性强。但当用户文章多了，需要快速扫一眼时，提供 `--compact`：

```
$ peerpedia article list --mine --compact
| ID       | Title          | Status        | ★   |
|----------|----------------|---------------|-----|
| 47203b30 | Published Paper| sedimentation | 4.0 |
| cad3e7c4 | Draft Paper    | draft         |  —  |
```

默认保留 panel，`--compact` 给熟练用户快速浏览。

### 20. `--sortby` 排序选项

`article list` 目前按创建时间排序，无法按内容质量筛选：

```
$ peerpedia article list --sortby originality
$ peerpedia article list --sortby forks
$ peerpedia article list --sortby relevance   ← 综合评分 + 社会信号
```

支持维度：`originality`, `rigor`, `completeness`, `pedagogy`, `impact`, `score`（综合）, `forks`, `created`, `updated`, `relevance`（默认）。

### 20. 全局 `--yes`/`-y` flag

统一所有不可逆操作的跳过确认机制。`delete` 已有 `[y/N]`，扩展到 `publish`、`merge accept`、`account delete`。

---

## 优先级建议

| 优先级 | 编号 | 理由 |
|--------|------|------|
| **高** | #1, #3, #4 | 新用户前 5 分钟的决定性体验 |
| **高** | #6, #7, #8 | 空状态是流失点，也是引导机会 |
| **中** | #12, #15 | silent failure + 噪音，用户容易误解 |
| **中** | #9, #10 | 不可逆操作安全网 + 幂等反馈 |
| **低** | #13, #14 | review 细节打磨 |
| **低** | #17, #18, #19, #20 | 锦上添花 |

大部分改动是**单行字符串替换**级别——改提示文字、加一行输出。不动架构、不动数据模型、不需要新依赖。
