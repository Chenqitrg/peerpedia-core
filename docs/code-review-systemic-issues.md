# CLI 系统性问题审查

**日期:** 2026-06-25 – 2026-06-26
**方法:** 用户测试 + 源码追踪 + 模式 grep 扫描
**范围:** CLI handlers、helpers、transport、commands 调用链

---

## 一、调试方法

三步循环：

1. **把玩** — 以新用户身份运行命令，观察输入/输出/错误
2. **追踪** — 从 handler → commands → transport/storage，追调用链
3. **扫描** — 用 grep 验证某个模式在**所有** handler 中是否一致

关键优势：CLI 是纯文本界面，从"用户看到什么"到"源码哪里写的"是一条直线，零上下文切换。

---

## 二、Server 模型

### 设计

每个人跑自己的 server，serve 自己的数据。`PEERPEDIA_SERVER` = "我的 server"。

```
Alice 的 server     → Alice 的 articles/follows/followers 的权威来源
Bob 的 server       → Bob 的 articles/follows/followers 的权威来源
```

### 问题：authoritative 判断有歧义

`discover_following()` 中：

```python
home_server = os.environ.get("PEERPEDIA_SERVER")
authoritative = (server == home_server)
```

这个判断只问了"是不是我的 server"，没问"查的是不是我的数据"。查 Bob 的 followers 但连 Alice 的 server 时，也会被当作 authoritative。

**建议：** `authoritative` 应由 handler 层显式传入，不在 `discover_*` 内部猜测。

### 问题：`_pull_social` 对所有 peer 查询同一用户

`follow` 后调用 `_pull_social(db, followed_id)`，遍历所有 known peers 查询 Bob 的数据。但只有 Bob 的 server 是权威的，其他 server 不应该被查询。

### Server 端点认证矩阵

| 端点 | 认证 |
|------|------|
| `/health` | 公开 |
| `/api/v1/school` | 公开 |
| `/api/v1/articles/{id}/head` | 公开 |
| `/api/v1/articles/{id}/bundle` | 公开 |
| `/api/v1/articles/{id}/ancestor/{hash}` | 公开 |
| `/api/v1/articles/{id}/repo` | 公开 |
| `/api/v1/users/{id}/following` | 公开 |
| `/api/v1/users/{id}/followers` | 公开 |
| `/api/v1/users/{id}/articles` | 公开 |
| `/api/v1/search` | 需 Ed25519 |
| `/api/v1/articles/{id}` | 需 Ed25519 |
| `/api/v1/peers` | 需 Ed25519 |

---

## 三、ID 解析一致性

### 现有解析函数

| 函数 | 解析顺序 | 返回 |
|------|---------|------|
| `_resolve_article_id(db, ref)` | UUID → prefix → title search | `Article` 对象 |
| `_resolve_user(db, ref)` | @name → UUID → prefix → name search | user ID 字符串 |

### 问题：部分 handler 不解析就传给 server

Server 的 `/api/v1/users/{id}/*` 端点要求完整 UUID。但以下 handler 把 `args.user` 原始值直接传给 transport：

| Handler | 传值 | Server 行为 |
|---------|------|-----------|
| `_cmd_following` | `args.user` 裸传 | 短前缀 → 400 |
| `_cmd_followers` | `args.user` 裸传 | 短前缀 → 400 |
| `_cmd_article_list --user` | `args.user` 裸传 | 短前缀 → 400 |

对比正确做法（`follow`/`unfollow`/`alias`）：

```python
followed_id = _resolve_user(db, args.user_identifier)  # 先解析
_push_social("follow", follower_id=..., followed_id=followed_id)
```

### 建议

所有涉及 `--user` 且调用 server 的 handler 统一加 `_resolve_user()` 前置步骤。或在 `_resolve_server_url` 之后、transport 调用之前加一个统一的 resolve 层。

---

## 四、输出模式一致性

### 设计意图

```
CLI 无参数 → --json 默认（给 AI）
CLI --rich  → Rich panel（给人）
REPL       → --rich 默认（给人）
```

### 问题：`_output_result` 没被用

`helpers.py` 已封装：

```python
def _output_result(args, result, success_msg):
    if getattr(args, "json", False):
        _json_out(result)
    else:
        _ok(success_msg)
```

但只有 `maintainers.py` 使用了。其余 30+ 处全是手写 `if args.json: ... else: ...`。

### 问题：部分 handler 可能缺少 JSON 路径

手写模式容易遗漏 JSON 分支。例如 `article delete` 只能输出 human 格式。

---

## 五、Sync / 离线队列一致性

### 现有机制

| 函数 | 作用 |
|------|------|
| `_try_sync(db)` | 在线时立即推送到 server，best-effort |
| `_queue_if_offline(id)` | 离线时将 article ID 写入 `pending_ops.json` |

### 问题：覆盖不全

```
                    _try_sync    _queue_if_offline
article create       ✅           ✅
article edit         ✅           ✅
article publish      ✅           ✅
review submit        ✅           ❌
review reply         ✅           ❌
fork                 ✅           ❌
merge accept         ✅           ❌
follow/unfollow      ✅           ❌
maintainer add/rm    ❌           ❌
```

三层问题：
1. `_queue_if_offline` 只在 `articles.py` 中定义，其他 handler 未导入
2. `maintainer` 连 `_try_sync` 都没调
3. `_try_sync` 内部的 `discover_articles` 用 `_get_session_user()` 发现自己的文章——不是发现新内容，是刷新已有 metadata

### 建议

- `_queue_if_offline` 提升到 `bundle_utils.py`，所有 mutation handler 统一调用
- maintainer 操作加 `_try_sync`
- `_try_sync` 的 discovery 步骤改为 `discover_network(depth=1)`

---

## 六、Review Invite 的 Scoring Regression

### 问题链

```
invite_reviewer()
  └─ Review(scores={}, commit_hash="pending")   # 空 scores 的 pending 记录
       └─ recompute_article_score()
            └─ 遍历所有 Review 包括 pending
                 └─ r["scores"]["originality"]  # KeyError!
```

### 根因

`invite_reviewer` 创建了一个 `scores={}` 的 Review 占位记录。`recompute_article_score` → `aggregate_review_scores` 对此无防御，遍历所有 Review 时对空 scores 取 dimension key 崩溃。

### 建议

两处修：`invite_reviewer` 不应创建有商业意义的 Review 记录（用单独的 Invitation 表），或 `recompute_article_score` 跳过 `scores` 为空/不完整的 Review。

---

## 七、Handler 辅助函数采纳度

| 辅助函数 | 设计用途 | 实际使用 |
|---------|---------|---------|
| `_resolve_user` | 统一用户引用解析 | 3 个 handler 用，3 个 handler 没用 |
| `_require_resolved_article` | 解析 + integrity check | 2 个 handler 用，15+ 个 handler 用裸 `_resolve_article_id` |
| `_output_result` | 统一 JSON/Rich 分支 | 1 个 handler 用，30+ 处手写 if/else |
| `_queue_if_offline` | 离线排队 | 只有 `articles.py` 内使用 |

### 根因

辅助函数定义在 `helpers.py` 但新增 handler 时没有强制使用。没有 lint 规则、没有 code review checklist。

### 建议

- `_output_result` 推广到所有 handler——可以逐步替换
- `_require_resolved_article` 推广到所有 mutation handler（review submit、maintainer、fork 等）
- `_queue_if_offline` 提升到 `bundle_utils.py` 并导入到所有 mutation handler

---

## 八、非 TTY 处理

### 现状

`article create` 已加了 `isatty()` 检测（line 53）。其他弹编辑器的 handler 还没：

| Handler | 弹编辑器 | TTY 检测 |
|---------|---------|---------|
| `article create` | 是 | ✅ |
| `article edit` | 是 | ❌ |
| `review reply` | 是 | ❌ |

### 建议

`_open_editor()` 和 `_prompt_commit_message()` 在内部加 `isatty()` 检测，而非每个 handler 手动检测。

---

## 九、修复状态追踪（更新至 2026-06-26 第三轮）

### 已修复

| 问题 | 状态 |
|------|------|
| 创建文章不显示 ID | ✅ |
| `article list` 默认含 draft | ✅ |
| `sync pull` → 401 | ✅ |
| `review invite` → NameError | ✅ |
| `review rate` → NameError | ✅ 但引入了新 bug（见下） |
| `bookmark remove` 假成功 | ✅ |
| Share 显示完整 UUID | ✅ |
| Dashboard on `peerpedia` | ✅ |
| `--rich` flag（顶层命令） | ✅ |
| `account register` 覆盖提示 | ✅ |
| `article create` TTY 检测 | ✅ |
| article publish 显示 review window + next | ✅ |

### 仍存在

| 问题 | 状态 |
|------|------|
| REPL `s-enter` 崩溃 | ❌ |
| `compile --format pdf` 静默忽略 | ❌ |
| 密码 echo 警告 (macOS) | ❌ |
| `--rich` 子命令不支持 | ❌ 第三轮新发现 |
| feed 泄露 draft 给 follower | ❌ 第三轮新发现 |

### 第三轮新 regression

| 问题 | 说明 |
|------|------|
| `review rate` → AttributeError | `_resolve_user` 返回 str 被当 User 对象调用 `.id` |
| `review invite` → Article not found | `args.article_id` 未解析（见 #18） |

### 第三轮新发现的系统性缺陷

| # | 问题 | 影响范围 |
|---|------|---------|
| 18 | `args.article_id` 6 个 handler 未解析 | review invite/rate、fork、bookmark add/remove、share push |
| 19 | `review rate` 二次 regression | 仅 _cmd_review_rate |
| 20 | `--rich` 子命令 scope | review list、merge 等子命令 |
| 21 | feed 隐私泄露 | `article list --feed` 未过滤 draft |
