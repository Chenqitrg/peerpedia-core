# PeerPedia Core — Architecture

## 文件树

```
peerpedia_core/
├── __init__.py
├── cli.py                    # 命令行入口（argparse + Rich）
│   │                         #   account register/whoami
│   │                         #   article create/edit/show/list/publish/delete
│   │                         #   review submit/list
│   │                         #   fork / merge propose/accept
│   │                         #   bookmark add/list
│   │                         #   compile
│   │                         #   sync status/push
│   │
├── repl.py                   # 交互式 REPL（prompt_toolkit）
├── commands.py               # 业务编排层（create_article_with_content、fork_article、submit_review…）
├── exceptions.py             # 自定义异常（NotFound、NotAuthorized、Conflict、BadRequest）
│
├── config/
│   └── params.py             # 全局可调参数（沉淀天数、评分权重、评论长度限制）
│
├── policies/
│   └── articles.py           # 权限检查（谁能读/写/fork/publish/download/sync）
│
├── storage/                   # Local Domain — 永远活着
│   ├── git_backend.py        #   纯本地 Git（init/commit/history/diff/merge/delete）——不依赖 sync/
│   ├── compiler.py           #   编译后端（Markdown→HTML、Typst→PDF/SVG/PNG）
│   ├── locks.py              #   文件锁（并发写保护）
│   └── db/
│       ├── engine.py         #   SQLAlchemy 引擎 + JSONList/JSONDict 类型 + init_db
│       ├── models.py         #   ORM 模型（Article、User、Review、Follow、Bookmark…）
│       ├── session_utils.py  #   事务装饰器（commit/rollback/session 生命周期）
│       ├── crud_article.py   #   Article CRUD
│       ├── crud_user.py      #   User + Follow CRUD
│       ├── crud_review.py    #   Review CRUD
│       ├── crud_bookmark.py  #   Bookmark CRUD
│       ├── crud_merge.py     #   MergeProposal CRUD
│       └── crud_citation.py  #   Citation CRUD
│
├── sync/                      # Sync Domain — 联网同步
│   ├── git_bundle.py         #   git bundle 协议（create/apply/find_common_ancestor/is_ancestor）
│   │                         #   自包含：只依赖 GitPython + monotonic_search，不依赖 git_backend
│   ├── monotonic_search.py   #   k-exponential 搜索算法（纯算法，无 git/HTTP 依赖）
│   ├── bundle_client.py      #   客户端 sync 编排（调 git_bundle + transport/http + git_backend）
│   ├── bundle_server.py      #   服务端 handler（调 git_bundle + git_backend，不含 HTTP 代码）
│   ├── transport/
│   │   ├── __init__.py
│   │   └── http.py           #   HTTP 传输实现（唯一 import httpx 的文件）← 可插拔替换
│   ├── network.py            #   网络检测（is_online）
│   └── pending_queue.py      #   离线操作队列
│
├── workflow/
│   ├── scoring.py            # 评分聚合（加权平均）
│   ├── sedimentation.py      # 沉淀池自动发布
│   └── reputation.py         # 声誉计算（EMA 平滑）
│
└── types/
    └── scores.py             # 五维评分（FiveDimScores）+ 四维声誉（ReputationScores）

tests/
├── conftest.py               # 共享 fixture（临时 SQLite 引擎）
├── conftest_backend.py       # [死代码] 引用不存在的 peerpedia_api
├── e2e.sh                    # 端到端黑盒测试（CLI 命令 + 断言）
├── test_commands.py          # 编排层测试（fork、rollback、create、update）
├── test_crud.py              # DB CRUD 测试（Article、Review、User、Follow、Bookmark…）
├── test_crud_article.py      # Article 列表/计数测试
├── test_models.py            # ORM 模型测试
├── test_git_backend.py       # Git 操作测试
├── test_policies.py          # 权限测试
├── test_reputation.py        # 声誉计算测试
├── test_sedimentation_publish.py  # 沉淀池自动发布测试
├── test_workflow.py          # 评分/沉淀/声誉 workflow 测试
├── test_session_utils.py     # 事务装饰器测试
├── test_params.py            # 参数配置测试
├── test_types.py             # 类型测试
├── test_sync.py              # 同步模块测试
├── test_monotonic_search.py  # k-exponential 搜索算法测试
├── test_exceptions.py        # 异常类测试
└── test_seed.py              # 种子数据验证
```

## 两大域

详细信息见 [peerpedia-architecture.svg](peerpedia-architecture.svg)。

```
┌── Local Domain（永远活着）────┐  ┌── Sync Domain（联网同步）──┐
│                               │  │                              │
│  cli.py ── sync push ─────────────→ bundle_client.py             │
│   │                           │  │   │         ↕ HTTP            │
│   │  (HTTP 路由层 ── req ───────→ bundle_server.py              │
│   │   未来：server/main.py)     │  │   │          │              │
│   │       │                   │  │   ├──────────┤              │
│   ├───────┤                   │  │   │  git_bundle.py            │
│   │       │                   │  │   │  (自包含，不依赖         │
│   ▼       ▼                   │  │   │   git_backend)           │
│ commands.py                   │  │   │          │              │
│   │       │                   │  │   │  monotonic_search.py     │
│   ├──┬────┴───┬──────┐        │  │   │  (纯算法)                │
│   ▼  ▼        ▼      ▼        │  │   │          │              │
│ poli- db   git_backend work   │  │   │  transport/http.py       │
│ cies    ◄──────────── flow     │  │   │  (唯一 import httpx)    │
│   │                            │  │   │                          │
│   │  ★ 所有模块都经过这里       │  │   │                          │
│   │                            │  │   │                          │
│   ├── storage/compiler.py      │  │   │                          │
│   ├── storage/locks.py         │  │   │                          │
│   └── storage/db/{crud_*,      │  │   │                          │
│           models, engine}.py   │  │   │                          │
│                               │  │                              │
└───────────────────────────────┘  └──────────────────────────────┘

跨域接口（只有一条）：
  ① CLI → bundle_client      触发 sync push
```

**规则：**
- **Git 是内容 SOT**——正文和评审内容存在 Git 仓库中，DB 只存元数据和评分缓存
- **commands.py 是唯一的数据接口**——所有模块要接触 git_backend 或 storage/db，必须经过 commands.py
- **Sync Domain 自包含**——`git_bundle.py` 不依赖 `git_backend`，只依赖 GitPython + `monotonic_search`。`bundle_client.py` 和 `bundle_server.py` 独立调用 `git_backend` 做 git 操作
- **HTTP 可插拔**——`transport/http.py` 是 Sync Domain 里唯一 import `httpx` 的文件。换协议只需替换 `transport/`
- **Local Domain 不知道 Sync Domain**——`git_backend.py` 和 `commands.py` 不 import 任何 `sync/` 下的模块

## Sync 模块拆分

之前的 `sync/bundle_sync.py`（混合了 git 操作、HTTP 调用、sync 编排）已删除，拆分为：

| 模块 | 职责 | 依赖 |
|------|------|------|
| `sync/git_bundle.py` | git bundle 协议：`create_bundle` / `apply_bundle` / `find_common_ancestor` / `is_ancestor` | GitPython + `monotonic_search` |
| `sync/monotonic_search.py` | k-exponential 搜索算法（`search_monotonic_boundary`） | 纯 Python，无外部依赖 |
| `sync/bundle_client.py` | 客户端 sync 编排：`client_sync` / `client_pull_incremental` / `client_push_incremental` / `client_create_article` / `client_find_merge_base` | `git_bundle` + `transport/http` + GitPython |
| `sync/bundle_server.py` | 服务端 handler：`serve_get_head` / `serve_post_sync` / `serve_get_bundle` / `serve_get_ancestor` / `serve_post_articles` | `git_bundle` + GitPython（不含 HTTP 代码） |
| `sync/transport/http.py` | HTTP 传输实现：`fetch_head` / `push_bundle` / `fetch_bundle` / `ancestor_probe` / `post_article` | `httpx`（唯一） |
| `sync/network.py` | 网络检测：`is_online(server_url)` | `httpx` |
| `sync/pending_queue.py` | 离线操作队列（`~/.peerpedia/pending_ops.json`） | 文件 I/O |

### bundle_client ↔ bundle_server 函数镜像

```
     CLIENT (bundle_client.py)           SERVER (bundle_server.py)
     ───────────────────────────           ─────────────────────────
     client_sync() → 编排 push/pull      被 HTTP 路由层调用
       ├─ client_pull_incremental        ├─ serve_get_head()
       │    → fetch_bundle(HTTP)         │    → git.Repo.head.commit.hexsha
       │    → apply_bundle()             │
       ├─ client_push_incremental        ├─ serve_post_sync()
       │    → create_bundle()            │    → apply_bundle(ff_only=True)
       │    → push_bundle(HTTP)          │
       ├─ client_create_article          ├─ serve_get_bundle()
       │    → post_article(HTTP)         │    → create_bundle()
       │                                 │
       └─ client_find_merge_base         ├─ serve_get_ancestor()
            → ancestor_probe(HTTP)       │    → is_ancestor()
            → find_common_ancestor()     │
                                         └─ serve_post_articles()
                                              → tar.gz 解包
```

### 同步协议

```
本地 A                                  对等节点 B
───────                                 ──────────

1. GET  /api/v1/articles/{id}/head      ← B 的 HEAD hash

2. 如果 B 有新提交：
   GET  /api/v1/articles/{id}/bundle?since=<A_head>
   ← 增量 bundle，本地 apply_bundle()

3. 如果 A 有新提交：
   create_bundle(repo, B_head)            → 增量 bundle
   POST /api/v1/articles/{id}/sync        → B apply_bundle(ff_only=True)

4. 首次推送（B 没有这篇文章）：
   tar.gz → base64 → POST /api/v1/articles → B 解包 + init repo

祖先检测：k-exponential probe（monotonic_search）
  - 在本地 commit 历史上做指数跳探（1, k, k², …）
  - 每个 probe 是一次 HTTP GET /ancestor/{hash}
  - 找到边界后二分精确定位 merge base
```

## 服务器架构（peerpedia serve）

`peerpedia serve` 是**计划中**的子命令，尚未实现。当前 `bundle_server.py` 包含服务端逻辑（纯函数，无 HTTP），等待 HTTP 路由层（`server/main.py`）调用。

### 规划中的完整调用关系


**关键：**
- HTTP 层（`server/main.py`，未来）只做 JWT + 权限 + 调用 `bundle_server`。不包含业务逻辑。
- 它们直接调 `git_backend`（+ CRUD for bundle_server），是 git 操作的传输层。
- `commands.py` 是 CLI 操作的编排层，调 `git_backend` + CRUD + policies + workflow。
- `bundle_client.py` 和 `bundle_server.py` **互不 import**，通过 HTTP 传输 bundle 通信。

## 数据模型

```
User ──< ArticleAuthor >── Article ──< Citation >── Article
 │                              │
 │                              ├── Review (reviewer=User, article=Article)
 │                              ├── Bookmark (user=User, article=Article)
 │                              └── MergeProposal (fork_article=Article, target=Article)
 │
 └──< Follow >── User
      follower_id / followed_id
```

| 模型 | 表 | 关键字段 |
|------|-----|---------|
| `User` | users | id, username, name, affiliation, reputation(JSON), password_hash |
| `Article` | articles | id, title, status(draft/sedimentation/published), score(JSON), forked_from, compiled_cache |
| `ArticleAuthor` | article_authors | article_id, author_id, position |
| `Review` | reviews | article_id, reviewer_id, scope(self/pool), commit_hash, scores(JSON) |
| `Follow` | follows | follower_id, followed_id (联合唯一) |
| `Bookmark` | bookmarks | user_id, article_id (联合唯一) |
| `MergeProposal` | merge_proposals | fork_article_id, target_article_id, status(open/accepted/rejected) |
| `Citation` | citations | from_article_id, to_article_id, forward_prob, backward_prob |

## 关键函数

### 编排层 (commands.py，顶层)

| 函数 | 写入顺序 | 说明 |
|------|---------|------|
| `create_article_with_content()` | Git → DB | 先 init repo + commit 正文，再建 DB 行 |
| `update_article_content()` | Git → DB | 先 commit 新内容，再更新 DB 元数据 |
| `fork_article()` | Git → DB | 先 git clone 原 repo，再从 git 推导作者，最后建 DB 行 |
| `rollback_article()` | Git → DB | 先 checkout 旧版 + commit，再更新 DB |
| `publish_article()` | Git → DB | 先写自评到 git（scores.json + threads/），再更新 DB 状态和评分 |
| `submit_review()` | Git → DB | 评审文件先落 Git（reviews/{id}/scores.json + threads/），成功后才写 DB 评分缓存 |
| `accept_merge()` | Git → DB | 先 git merge fork 到 target，再从 git 推导作者，最后更新 DB |

### DB CRUD (storage/db/)

| 文件 | 关键函数 |
|------|---------|
| `crud_article.py` | `create_article`, `get_article`, `list_articles`, `update_article_status`, `delete_article`, `add_article_authors`, `get_author_ids`, `increment_fork_count`, `set_sink_start` |
| `crud_user.py` | `create_user`, `get_user`, `get_user_by_name`, `follow_user`, `unfollow_user`, `get_followers`, `get_following`, `get_follower_count` |
| `crud_review.py` | `create_review`, `get_reviews_for_article`, `update_review_scores`, `upsert_review` |
| `crud_bookmark.py` | `add_bookmark`, `remove_bookmark`, `get_bookmarks_for_user`, `is_bookmarked` |
| `crud_merge.py` | `create_merge_proposal`, `accept_merge_proposal`, `get_merge_proposal` |
| `crud_citation.py` | `create_citation`, `update_citation_probabilities` |

### Git 操作 (git_backend.py)

| 函数 | 职责 |
|------|------|
| `init_article_repo(repo_path)` | 创建 Git 仓库 + reviews/ 目录 |
| `commit_article(repo_path, message, author_name, author_email)` | 提交工作区改动 |
| `get_commit_history(repo_path)` | 获取提交历史 |
| `get_commit_authors(repo_path)` | 从 git commit email 提取作者列表 |
| `get_diff_between(repo_path, hash1, hash2)` | 两个 commit 之间的 diff |
| `merge_git_repos(target, fork, author_name)` | Git merge fork 到 target |
| `delete_article_repo(repo_path)` | 删除文章 Git 仓库 |

### Git Bundle 协议 (sync/git_bundle.py)

| 函数 | 职责 |
|------|------|
| `create_bundle(repo_path, since_hash) → bytes` | 创建增量 git bundle |
| `apply_bundle(repo_path, bundle_bytes, ff_only=True) → str` | 应用 bundle（fast-forward 或 merge），返回新 HEAD |
| `is_ancestor(repo_path, maybe_ancestor) → bool` | 检查一个 hash 是否为 HEAD 的祖先 |
| `find_common_ancestor(repo_path, probe, server_head, k=5) → str \| None` | 通过 k-exponential probe 找到与远程的共同祖先 |

### 同步客户端 (sync/bundle_client.py)

| 函数 | 职责 |
|------|------|
| `client_sync(server, article_id) → dict` | 客户端 sync 编排：find merge base → pull/push/merge |
| `client_find_merge_base(server, article_id, repo_path, server_head) → str \| None` | 通过 k-exponential probe 找到与服务器的共同祖先 |
| `client_pull_incremental(server, article_id, since_hash, ff_only=True) → str \| None` | 拉取增量 bundle 并 apply |
| `client_push_incremental(server, article_id, since_hash, to_hash) → str \| None` | 创建增量 bundle 并推送 |
| `client_create_article(server, article_id) → bool` | 首次推送：tar.gz 全量上传 |

### 同步服务端 (sync/bundle_server.py)

| 函数 | 职责 |
|------|------|
| `serve_get_head(repo_path) → str \| None` | 返回 HEAD hash |
| `serve_post_sync(repo_path, bundle_bytes) → str` | 接受并 apply bundle（ff-only） |
| `serve_get_bundle(repo_path, since_hash) → bytes \| None` | 返回增量或全量 bundle |
| `serve_get_ancestor(repo_path, hash) → bool` | 检查 hash 是否为 HEAD 祖先 |
| `serve_post_articles(repo_path, payload) → str` | 解包 tar.gz 创建新文章 repo |

### HTTP 传输 (sync/transport/http.py)

| 函数 | 职责 |
|------|------|
| `fetch_head(server, article_id) → str \| None` | GET /head |
| `push_bundle(server, article_id, bundle_bytes) → str` | POST /sync → "ok" / "conflict" / "error" |
| `fetch_bundle(server, article_id, since_hash) → bytes \| None` | GET /bundle?since= |
| `ancestor_probe(server, article_id) → Callable` | 返回 probe callback 给 `find_common_ancestor` |
| `post_article(server, article_id, bundle_b64) → bool` | POST /articles（首次推送） |

### 权限 (policies/articles.py)

| 函数 | 检查内容 |
|------|---------|
| `assert_can_read_article()` | 作者本人 / 公开文章 / 沉淀池文章（认证用户） |
| `assert_can_edit_article()` | 只有作者本人，且状态为 draft/published |
| `assert_can_fork_article()` | 只有 published 状态，且未 fork 过 |
| `assert_can_publish_article()` | 只有作者本人 |
| `assert_can_submit_review()` | sedimentation 或 published 状态 |
| `assert_can_download_content()` | 作者本人 / published |
| `assert_can_sync_article()` | 只有作者本人，且状态为 draft/published |

## Git 仓库结构

每篇文章是一个独立的 Git 仓库：

```
~/.peerpedia/articles/{article_id}/
├── .git/
├── article.md                  # 文章正文 + 元数据（YAML frontmatter）
└── reviews/
    ├── {reviewer_a}/
    │   ├── scores.json         # 评审评分（JSON，机器直接读）
    │   └── threads/
    │       ├── 001.md          # 评审意见（按时间排序）
    │       ├── 002.md          # 作者回复
    │       └── ...
    └── {author}/
        ├── scores.json         # 作者自评（和其他评审同格式）
        └── threads/
```

### 文章文件格式（`article.md` / `article.typ`）

```markdown
---
title: A Note on Tensor Networks
abstract: Tensor networks provide a powerful framework for...
keywords: [tensor networks, quantum physics]
categories: [physics, mathematics]
---

# Introduction

正文内容...
```

YAML frontmatter 存 title、abstract、keywords、categories——这些字段在 git 中有版本历史，DB 只是查询缓存。

### 评审存储格式（`reviews/{reviewer_id}/`）

```
reviews/{reviewer_id}/
├── scores.json              ← 评分（5 维 JSON），每次提交覆盖
└── threads/
    ├── 001.md               ← 首次评审
    ├── 002.md               ← 作者回复
    └── ...                  ← 序号递增，按时间追加
```

- **`scores.json`**：`{"originality": 4, "rigor": 3, ...}`，机器原生格式，`json.load()` 一行
- **`threads/`**：每个评论是独立文件，按 `001.md`, `002.md` 排序。Git diff 干净，不需要解析大文件
- **自评同等**：作者自评存在 `reviews/{author_id}/`，格式完全一样
- **匿名评审**：sedimentation 阶段评审人目录名是 `sha256(article_id:reviewer_id)` 的前 12 位，保护评审人身份

## 数据流：一个评审的完整路径

```
用户敲: peerpedia review submit abc123 --scores ... --user feynman

cli.py:
  1. _resolve_user("feynman") → user_id
  2. 调用 submit_review(db, "abc123", user_id, scores, ...)

commands.py → submit_review():
  3. get_user(db, reviewer_id) → 确认评审人存在
  4. assert_can_submit_review(db, article_id) → 确认文章可评审
  5. _write_review_to_git():
     a. 写 reviews/{reviewer_id}/scores.json
     b. 写 reviews/{reviewer_id}/threads/{nnn}.md
     c. git commit
  6. upsert_review() → 写 DB 评分缓存
  7. compute_article_score(db, article_id) → 重新算文章总分
  8. compute_author_reputation(db, author_id) → 更新作者声誉

cli.py:
  9. db.commit()
  10. 显示 ✓ Review submitted + 星级评分
```

## 文章状态机

```
                   publish + self_review
    ┌──────┐ ─────────────────────────► ┌──────────────┐
    │draft │                            │sedimentation │  限时公开评审
    └──┬───┘                            └──────┬───────┘
       │ edit → 内容更新（新 commit）           │ timeout → publish_ready_articles()
       │ delete → 删除                          │ extend → 延长沉淀期
       ▼                                        ▼
     删除                                  ┌──────────┐
                                           │published │  公开发表，可 fork
                                           └──────────┘
```

## 数据目录

所有数据存在 `~/.peerpedia/`：

```
~/.peerpedia/
├── peerpedia.db          ← SQLite 数据库（元数据：状态、评分缓存、作者列表）
├── pending_ops.json      ← 离线操作队列
└── articles/
    └── {article_id}/
        ├── .git/          ← Git 仓库（完整内容历史）
        ├── article.md     ← 文章正文 + 元数据（YAML frontmatter）
        └── reviews/
            └── ...
```

备份只需要复制整个 `~/.peerpedia/` 目录。

## 设计规则（写代码时遵守）

1. **Git 存内容，DB 存缓存** — Git 仓库存正文 + 评审文件（SOT），DB 存评分缓存 + 元数据（status、fork_count）。评分缓存从 Git 重新计算，不独立编造
2. **Git-first，DB 后写** — 所有内容先落 Git（commit），成功后才写 DB。Git 失败 → DB 不写
3. **Git 与 DB 互不知晓** — 两个存储层不互相 import，只有 commands.py 知道两者
4. **Fail fast** — 无 Git → 报错，不静默降级。参数不该为 None 时立即抛异常
5. **编排函数不 commit** — commands.py 只做 add/flush，CLI 调 db.commit()
6. **评审是文件夹，评分和评论分离** — `reviews/{id}/scores.json` + `threads/` 子目录，每个评论是独立文件
7. **自评即评审** — 作者自评存在 `reviews/{author_id}/`，和其他评审同格式同流程
8. **Sync Domain 自包含** — `git_bundle.py` 不依赖 `git_backend.py`。`transport/http.py` 是唯一 import `httpx` 的文件
9. **两端同构** — 客户端和服务器运行同一套代码，区别只在数据目录内容和启动命令
