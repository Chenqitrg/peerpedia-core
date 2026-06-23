# Review 文件阅读顺序

## 总原则

**从外到内，从抽象到具体，从不变到易变。**

先理解架构约束和分层规则，再看数据结构和权限，最后看业务逻辑。如果顺序反了——比如先看 `cli/`——你会被实现细节淹没。

---

## 第一遍：建立心智模型（必读，按顺序）

| 序号 | 文件 | 读什么 | 耗时 |
|------|------|--------|------|
| 1 | [architecture.md](architecture.md) | 分层结构、状态机、当前做法 | 10min |
| 2 | [exceptions.py](../peerpedia_core/exceptions.py) | 4 个异常类：`NotFoundError` / `NotAuthorizedError` / `ConflictError` / `BadRequestError` | 2min |
| 3 | [params.py](../peerpedia_core/config/params.py) | `SinkParams` / `ScoreParams` / `ReputationParams` 的默认值 | 3min |
| 4 | [models.py](../peerpedia_core/storage/db/models.py) | 7 个 ORM 类：字段、外键、UniqueConstraint | 8min |
| 5 | [scores.py](../peerpedia_core/types/scores.py) | `FiveDimScores`（5 维）和 `ReputationScores`（4 维） | 2min |

**第一遍的目标：** 能回答"文章有几种状态？评分有哪五个维度？权限检查用哪个异常？"

---

## 第二遍：理解核心机制（必读，按顺序）

底层模块——上层代码的正确性取决于它们。

| 序号 | 文件 | 读什么 | 为什么在这里 |
|------|------|--------|-------------|
| 6 | [engine.py](../peerpedia_core/storage/db/engine.py) | Engine 缓存、WAL + foreign_keys pragma、`JSONList`/`JSONDict` 类型 | DB 是所有模块的基础 |
| 7 | [git_backend.py](../peerpedia_core/storage/git_backend.py) | `init_article_repo` / `commit_article` / `get_commit_history` / `get_commit_authors` / `merge_git_repos` / `delete_article_repo` / `list_review_dirs` / `read_review_scores` | Git 是内容 SOT |
| 7b | [sync/git_bundle.py](../peerpedia_core/sync/git_bundle.py) | `create_bundle` / `apply_bundle` / `find_common_ancestor` / `is_ancestor` | git bundle 协议——自包含 |
| 7c | [sync/monotonic_search.py](../peerpedia_core/sync/monotonic_search.py) | `search_monotonic_boundary` — k-exponential 搜索 | 纯算法 |
| 8 | [policies/articles.py](../peerpedia_core/policies/articles.py) | 每个 `assert_can_*` 函数——谁可以读写/fork/publish | 权限集中表达 |
| 9 | [crud_article.py](../peerpedia_core/storage/db/crud_article.py) | `create_article` / `get_article` / `list_articles` / `set_sink_start` / `extend_sink` | 最复杂的 CRUD |

**第二遍的目标：** 能解释"Git commit 和 DB 记录的关系是什么？谁会先被创建？"

---

## 第三遍：理解分层——编排层 vs 纯计算层

`commands/` 是编排层，`workflow/` 是纯计算层。两者严格分离。

| 序号 | 文件 | 读什么 | 关键点 |
|------|------|--------|--------|
| 10 | [workflow/scoring.py](../peerpedia_core/workflow/scoring.py) | `aggregate_review_scores` — 加权平均，含 scope_weights | 纯函数，不依赖 DB |
| 11 | [workflow/reputation.py](../peerpedia_core/workflow/reputation.py) | `compute_reputation` / `blend_reputation` / `get_reviewer_weight` | 5 维→4 维映射，EMA 平滑 |
| 12 | [workflow/sedimentation.py](../peerpedia_core/workflow/sedimentation.py) | `is_ready_to_publish` / `apply_no_review_penalty` | 纯函数 |
| 13 | [commands/__init__.py](../peerpedia_core/commands/__init__.py) | re-export 清单——了解所有公开函数 | 入口索引 |
| 14 | [commands/articles.py](../peerpedia_core/commands/articles.py) | `create_article_with_content` / `update_article_content` / `publish_article` / `fork_article` / `rollback_article` | 文章生命周期 |
| 15 | [commands/reviews.py](../peerpedia_core/commands/reviews.py) | `submit_review` / `_write_review_to_git` | Git-first 评审写入 |
| 16 | [commands/merge.py](../peerpedia_core/commands/merge.py) | `accept_merge` | merge 后自动沉淀 |
| 17 | [commands/sync.py](../peerpedia_core/commands/sync.py) | `apply_sync_bundle` / `sync_reviews_from_worktree` / `sync_status_from_git` | sync 后同步评审到 DB |
| 18 | [commands/workflow.py](../peerpedia_core/commands/workflow.py) | `publish_ready_articles` / `recompute_article_score` / `recompute_author_reputation` | 读 DB → 调 workflow 纯函数 → 写 DB |

**第三遍的目标：** 能画出 `submit_review` 从 CLI 参数到最终 score 的完整调用链。理解为什么 `workflow/` 不能 import `storage/`。

---

## 第四遍：理解服务器与本地的关系

### 一句话回答最常被问的问题

**"服务器和本地安装的是同一套代码吗？"**

是的。`peerpedia-core` 就是唯一的代码库。和 `git` 一样——你既可以 `git commit`（本地），也可以 `git push`（联网），还可以 `git daemon`（充当服务器）。

**"storage 里哪些归服务器？哪些归本地？"**

同一套 `models.py`、同一个 `git_backend.py`、同一个 `crud_*.py`。区别不在代码，在数据目录的内容：

```
服务器 (~/.peerpedia/)                   本地 (~/.peerpedia/)
├── peerpedia.db                         ├── peerpedia.db
│   ├── articles (所有用户)              │   ├── articles (自己的 + pull 来的)
│   ├── users (所有注册用户)             │   ├── users (自己 + 交互过的人)
│   └── reviews (缓存)                   │   └── reviews (自己的评审缓存)
│                                        │
├── articles/                            ├── articles/
│   ├── <id1>/.git  (全部文章)           │   ├── <id1>/.git  (pull 的子集)
│   └── ...                              │   └── ...
```

peerpedia 是**本地优先（local-first）**：所有操作默认在本地完成，sync 是后台行为。

### 代码层面的分工

| 模块 | 客户端 | 服务器 | 说明 |
|------|--------|--------|------|
| `git_backend.py` | 需要 | 需要 | 两端都用 |
| `git_bundle.py` | 需要 | 需要 | 两端都用 |
| `models.py` | 需要 | 需要 | 同一套 ORM |
| `policies/articles.py` | 需要 | 需要 | 两端都用 |
| `workflow/*.py` | 需要 | 需要 | 纯计算，两端都用 |
| `bundle_client.py` | 需要 | 不需要 | 客户端 sync 编排 |
| `bundle_server.py` | 不需要 | 需要 | 服务端 handler |
| `social_server.py` | 不需要 | 需要 | 服务端社交发现 handler |
| `server/app.py` | 不需要 | 需要 | ASGI 路由 + 异常映射 |
| `transport/http.py` | 需要 | 不需要 | 只有客户端发起 HTTP |
| `discovery.py` | 需要 | 不需要 | 编排 fetch → merge |
| `commands/discover.py` | 需要 | 需要 | DB merge 操作 |
| `commands/` | 需要 | 不需要 | 编排层只在本地 |

### 同步协议：git bundle

每篇文章是独立 git repo。同步传 git objects 增量包：

```
本地 A                                  对等节点 B
───────                                 ──────────

1. GET  /api/v1/articles/{id}/head      ← B 的 HEAD hash

2. 如果 B 有新提交：
   GET  /api/v1/articles/{id}/bundle?since=<A_head>
   ← 增量 bundle，本地 apply_bundle()

3. 如果 A 有新提交：
   create_bundle(repo, B_head)            → 增量 bundle
   POST /api/v1/articles/{id}/sync        → B apply_bundle()

4. 首次推送：
   tar.gz → base64 → POST /api/v1/articles → B 解包
```

### 关键设计决策

1. **Fast-forward only。** 拒绝分叉历史（409）。
2. **Git 是 SOT。** 内容在 git，DB 是缓存。
3. **sedimentation 文章不可写。** 沉淀期不可 edit/rollback/sync。
4. **离线队列。** `pending_ops.json` 暂存离线操作。

### 阅读顺序

| 序号 | 文件 | 读什么 |
|------|------|--------|
| 19 | [sync/network.py](../peerpedia_core/sync/network.py) | `is_online(server_url)` |
| 20 | [sync/bundle_client.py](../peerpedia_core/sync/bundle_client.py) | 客户端 sync 编排（`sync_article`、`pull_incremental`、`push_incremental`） |
| 21 | [sync/bundle_server.py](../peerpedia_core/sync/bundle_server.py) | 服务端 handler（`get_head`、`get_bundle`、`apply_sync`、`check_ancestor`、`create_article`） |
| 22 | [sync/social_server.py](../peerpedia_core/sync/social_server.py) | 社交发现服务端 handler（`serve_get_following`、`serve_get_followers`、`serve_get_articles`） |
| 23 | [sync/discovery.py](../peerpedia_core/sync/discovery.py) | 编排 fetch → merge（`discover_following`、`discover_followers`、`discover_articles`） |
| 24 | [commands/discover.py](../peerpedia_core/commands/discover.py) | DB merge 操作（`merge_users`、`merge_follows`、`merge_article_meta`） |
| 25 | [sync/transport/http.py](../peerpedia_core/sync/transport/http.py) | HTTP 传输（唯一 import httpx） |
| 26 | [sync/transport/__init__.py](../peerpedia_core/sync/transport/__init__.py) | Transport facade（切换 P2P 时只改此文件） |
| 27 | [server/app.py](../peerpedia_core/server/app.py) | ASGI 应用工厂 + 路由 + 异常映射 |
| 28 | [sync/pending_queue.py](../peerpedia_core/sync/pending_queue.py) | 离线队列 |

**第四遍的目标：** 能解释为什么服务器和客户端安装同一个 pip 包。

---

## 第五遍：理解入口（最后读）

| 序号 | 文件 | 读什么 |
|------|------|--------|
| 29 | [cli/__init__.py](../peerpedia_core/cli/__init__.py) | `main()` 入口、启动扫描、命令 dispatch |
| 30 | [cli/parser.py](../peerpedia_core/cli/parser.py) | argparse 结构 |
| 31 | [cli/handlers/](../peerpedia_core/cli/handlers/) | 每个子命令的 handler（含 `server.py`） |
| 32 | [repl.py](../peerpedia_core/repl.py) | prompt_toolkit REPL、定时扫描 |
| 33 | [compiler.py](../peerpedia_core/compiler.py) | Markdown→HTML、Typst→PDF/SVG/PNG、frontmatter 解析 |

---

## 第六遍：按改动模块定位（日常 Review 用）

### 改动在 `commands/`

```
1. 先看 policies/articles.py —— 确认权限检查正确
2. 看涉及的 crud_*.py —— 确认 DB 操作（只 flush，不 commit）
3. 看 git_backend.py —— 确认 Git 操作有对应 DB 更新
4. 看 workflow/*.py —— 确认纯计算函数被正确调用
5. 看 cli/ —— 确认 commit 在入口层
```

### 改动在 `crud_*.py`

```
1. 先看 models.py —— 确认字段约束
2. 看 commands/ —— 确认调用方兼容
3. 看对应的测试文件 —— 确认测试覆盖
```

### 改动在 `git_backend.py`

```
1. 先看 commands/ —— 确认所有 Git 调用点兼容
2. 看 tests/test_git_backend.py —— 确认测试覆盖
3. 看 sync/bundle_client.py 和 sync/bundle_server.py —— 它们直接调 git_backend
```

### 改动在 `workflow/*.py`（纯计算层）

```
1. 先确认没有 import storage/ 或 Session —— 纯计算约束
2. 看 params.py —— 确认参数用 params.xxx 而非硬编码
3. 看 commands/workflow.py —— 确认编排层正确调用纯函数
4. 看对应的测试文件 —— 确认数值计算的边界条件
```

### 改动在 `policies/articles.py`

```
1. 先看 commands/ —— 确认每个 assert_can_* 的调用点
2. 看 cli/ —— 确认错误消息能展示给用户
3. 看 tests/test_policies.py —— 确认新增权限有测试
```

### 改动在 `sync/transport/`

```
1. transport/__init__.py 是 facade —— 确认所有公共符号都 re-export
2. transport/http.py —— 确认所有函数遵循相同的错误处理契约（httpx.HTTPError → TransportError）
3. bundle_client.py —— 确认它从 transport/（facade）import，而非直接从 http.py
4. discovery.py —— 确认 TransportError → ConnectionError 的转换正确
```

### 改动在 `server/`

```
1. 先看 sync/bundle_server.py 和 sync/social_server.py —— 确认 handler 签名
2. 看 server/app.py —— 确认路由匹配 client transport/http.py 的 URL 模式
3. 看 exceptions.py —— 确认异常映射覆盖所有 PeerpediaError 子类
4. 看 cli/handlers/server.py —— 确认 uvicorn 配置（workers=1）
5. 看 tests/test_server.py —— 确认 TestClient 覆盖所有路由和错误状态
```

### 新增 CLI 命令

```
1. 先看 cli/parser.py —— 确认参数定义
2. 看 cli/handlers/ —— 确认 handler
3. 看 commands/ —— 确认业务逻辑在编排层
4. 看 policies/ —— 确认权限
5. 看 tests/ —— 确认测试
```

---

## 快速跳转地图

| 你想知道 | 去这里 |
|---------|--------|
| 文章状态机？ | [architecture.md](architecture.md) 状态转换 |
| 评分怎么算？ | [workflow/scoring.py](../peerpedia_core/workflow/scoring.py) → `aggregate_review_scores` |
| 声誉怎么算？ | [workflow/reputation.py](../peerpedia_core/workflow/reputation.py) |
| 沉淀池自动发布？ | [commands/workflow.py](../peerpedia_core/commands/workflow.py) → `publish_ready_articles` |
| 如何创建文章？ | [commands/articles.py](../peerpedia_core/commands/articles.py) → `create_article_with_content` |
| 事务在哪 commit？ | CLI/REPL 入口层 |
| Git repo 在哪？ | `~/.peerpedia/articles/<id>/` |
| DB 在哪？ | `~/.peerpedia/peerpedia.db` |
| sync 协议？ | [sync/bundle_client.py](../peerpedia_core/sync/bundle_client.py) |
| HTTP 传输？ | [sync/transport/http.py](../peerpedia_core/sync/transport/http.py) |
| 服务端路由？ | [server/app.py](../peerpedia_core/server/app.py) |
| 社交发现？ | [sync/discovery.py](../peerpedia_core/sync/discovery.py) → [commands/discover.py](../peerpedia_core/commands/discover.py) |
| 异常语义？ | [exceptions.py](../peerpedia_core/exceptions.py) |
| 评审如何从 git 同步到 DB？ | [commands/sync.py](../peerpedia_core/commands/sync.py) → `sync_reviews_from_worktree` |
| 测试怎么写？ | [tests/conftest.py](../tests/conftest.py) → 临时 SQLite engine fixture |

---

## 反模式

- ❌ **从 cli/ 开始读**——你会看到 argparse、Rich 的噪音，错过架构约束
- ❌ **从 tests/ 开始读**——测试是验证层，不是解释层
- ❌ **跳过 architecture.md**——没有它你就只能在代码里反推分层规则
- ❌ **只读 diff 不读上下文**——改动的正确性取决于它所在模块的契约
- ❌ **用 client-server 思维理解 sync**——服务器是另一个跑同一套代码的节点
