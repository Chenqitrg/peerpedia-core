# PeerPedia Core — Architecture

## 文件树

```
peerpedia_core/
├── __init__.py
├── compiler.py               # 编译后端（Typst + Markdown → HTML/PDF/SVG/PNG）
├── exceptions.py              # 语义异常（NotFound / NotAuthorized / Conflict / BadRequest）
├── frontmatter.py             # YAML frontmatter 解析/构建（文章和评审共用）
├── repl.py                    # 交互式 REPL（prompt_toolkit + 定时扫描）
│
├── config/
│   └── params.py              # 全局可调参数（沉淀天数、评分权重、scope 权重）
│
├── policies/
│   ├── __init__.py
│   └── articles.py            # 权限检查（读/写/fork/publish/rollback/sync）
│
├── storage/                   # Local Domain
│   ├── __init__.py
│   ├── git_backend.py         #   本地 Git（init/commit/history/diff/merge/delete）
│   │                          #   + list_review_dirs / read_review_scores
│   ├── locks.py               #   文件锁（并发写保护）
│   └── db/
│       ├── __init__.py          #   Facade：re-export Session + engine 工具
│       ├── engine.py            #   SQLAlchemy 引擎 + JSONList/JSONDict 类型 + init_db
│       ├── models.py            #   ORM 模型（Article、User、Review、Follow…）
│       ├── session_utils.py   #   事务包装（commit/rollback 生命周期）
│       ├── crud_article.py    #   Article CRUD
│       ├── crud_user.py       #   User + Follow CRUD
│       ├── crud_review.py     #   Review CRUD
│       ├── crud_bookmark.py   #   Bookmark CRUD
│       ├── crud_merge.py      #   MergeProposal CRUD
│       └── crud_citation.py   #   Citation CRUD
│
├── commands/                  # 编排层——唯一同时接触 git 和 db 的层
│   ├── __init__.py            #   re-export 所有公共函数
│   ├── articles.py            #   create、update、publish、fork、rollback、delete
│   ├── reviews.py             #   submit_review、_write_review_to_git
│   ├── merge.py               #   accept_merge、create_merge_proposal
│   ├── sync.py                #   apply_sync_bundle、git_sync_reviews、git_sync_status
│   ├── workflow.py            #   publish_ready_articles、recompute_*、recalculate_all_reputations
│   ├── bookmarks.py           #   add_bookmark、list_bookmarks
│   └── users.py               #   create_user、get_user 等读写包装
│
├── workflow/                  # 纯计算层——零 storage 依赖
│   ├── scoring.py             #   aggregate_review_scores（加权平均）
│   ├── sedimentation.py       #   is_ready_to_publish、apply_no_review_penalty
│   └── reputation.py          #   compute_reputation、blend_reputation、get_reviewer_weight
│
├── sync/                      # Sync Domain——联网同步
│   ├── git_bundle.py          #   git bundle 协议
│   ├── monotonic_search.py    #   k-exponential 搜索算法
│   ├── bundle_client.py       #   客户端 sync 编排
│   ├── bundle_server.py       #   服务端 handler
│   ├── network.py             #   网络检测
│   ├── pending_queue.py       #   离线操作队列
│   └── transport/
│       ├── __init__.py
│       └── http.py            #   HTTP 传输（唯一 import httpx）
│
├── cli/                       # 命令行入口（argparse + Rich）
│   ├── __init__.py            #   main() 入口 + 启动扫描
│   ├── display.py             #   输出格式化（_ok / _die / _json_out / _print_table）
│   ├── helpers.py             #   基础设施（_resolve_user / _parse_scores / _open_editor）
│   ├── parser.py              #   argparse 解析器构建
│   ├── sync_utils.py          #   sync CLI 辅助
│   └── handlers/              #   命令 handler——每个子命令一个文件
│       ├── __init__.py
│       ├── account.py         #   register / whoami
│       ├── articles.py        #   create / show / list / edit / publish / delete / scan
│       ├── compile_.py        #   compile
│       ├── mother.py          #   综合命令入口
│       ├── reviews.py         #   submit / list
│       ├── social.py          #   fork / merge / bookmark
│       └── sync.py            #   status / push
│
└── types/
    └── scores.py              # 五维评分（FiveDimScores）+ 四维声誉（ReputationScores）
```

## 分层规则

```
┌─── cli/ / repl.py ──────────────────────────────┐
│  入口：创建 session，调编排函数，调 commit()       │
└────────────────────┬─────────────────────────────┘
                     │
┌─── commands/ ───────────────────────────────────┐
│  编排层：唯一能同时 import git_backend 和 db      │
│  不调 commit()——只调 flush()，commit 由入口负责   │
└────┬─────────────────────┬──────────────────────┘
     │                     │
┌────▼──────────┐  ┌───────▼──────────┐
│  storage/     │  │  workflow/       │
│  git + db     │  │  纯计算           │
│  (互不知晓)    │  │  (零 storage)     │
└───────────────┘  └──────────────────┘
```

**当前做法：**
- **Git 是内容 SOT**——正文和评审存在 Git 中，DB 只存元数据和评分缓存
- **commands/ 是唯一数据接口**——只有它能同时碰 git 和 db
- **workflow/ 是纯计算**——不 import `storage/`、`Session`，所有数据由 commands 传入
- **入口负责 commit**——crud 函数只调 `flush()`，commit 由 CLI/REPL 入口统一做
- **fail fast**——不静默跳过、不吞异常、不返回默认值

## 依赖规则

每个模块能 import 什么，不能 import 什么。写代码时的硬约束。

```
Local Domain                              Sync Domain
───────────                              ───────────

commands/               ──────────────►   sync/bundle_client.py
  ├── storage/db/                          │
  ├── storage/git_backend.py               ├── commands/          (only apply_sync_bundle)
  ├── policies/                            └── sync/git_bundle.py
  ├── workflow/                                    │
  ├── config/                                      └── sync/monotonic_search.py
  ├── exceptions/
  └── types/

sync/bundle_server.py                    sync/git_bundle.py
  ├── commands/          (only apply_*)     └── sync/monotonic_search.py
  └── sync/git_bundle.py
```

**进口规则：**

| 文件 | 可以 import | 不可以 import |
|------|-----------|-------------|
| `commands/` | `storage/`、`policies/`、`workflow/`、`config/`、`exceptions/`、`types/` | `sync/`、**GitPython**、**直接 `sqlalchemy`** |
| `storage/db/` | `models.py`、`engine.py`、SQLAlchemy | `commands/`、`git_backend.py`、`sync/` |
| `storage/git_backend.py` | GitPython、`pathlib`、stdlib | `storage/db/`、任何 `peerpedia_core` 模块** |
| `policies/` | `storage/db/`、`exceptions/` | `commands/`、`sync/`、**GitPython**、**直接 `sqlalchemy`** |
| `workflow/` | `config/`、`types/` | `storage/`、`commands/`、`Session`、`sync/` |
| `sync/bundle_client.py` | `commands/`（仅 `apply_sync_bundle`）、`sync/git_bundle.py`、`sync/transport/` | `storage/`、`policies/`、`workflow/` |
| `sync/bundle_server.py` | `commands/`（仅 `apply_sync_bundle`）、`sync/git_bundle.py` | `storage/`、`policies/`、`workflow/` |
| `sync/git_bundle.py` | `sync/monotonic_search.py`、GitPython | `storage/`、`commands/`、`policies/`、`workflow/` |
| `sync/monotonic_search.py` | `collections.abc`（stdlib only） | 任何 `peerpedia_core` 模块 |

**db 与 git_backend 互不知晓**——`storage/db/` 和 `storage/git_backend.py` 互不 import。只有 `commands/` 同时知道两者。

**workflow/ 是纯计算**——不 import `storage/`、不 import `Session`。所有数据由 `commands/` 传入。

**Sync Domain 自包含**——`git_bundle.py` 和 `monotonic_search.py` 零依赖 `storage/` 和 `commands/`。只通过 GitPython 操作裸 git 仓库。

**硬约束 — import git**——除 `storage/git_backend.py` 和 `sync/git_bundle.py`（含 `bundle_client` / `bundle_server`）外，任何模块不得 `import git`（GitPython）。所有 git 操作必须经过这两个模块的函数接口。

**硬约束 — 数据库库**——除 `storage/db/` 外，任何模块不得直接 `import sqlalchemy`。`Session` 类型通过 `storage/db/__init__.py` facade 转发（`from peerpedia_core.storage.db import Session`），不得通过 `sqlalchemy.orm` 直接导入。任何 `db.query()` / `session.query()` / `db.get(Model, id)` 调用必须封装为 CRUD 函数。

## 状态机

**draft → sedimentation**：`publish_article()`，仅 draft 可调。含自评检查。首次 7 天，重新进入 3 天。

**draft → draft**：`update_article_content()`、`rollback_article()`。内容变更，状态不变。

**draft → 删除**：`delete_article()`。

**sedimentation → published**：`publish_ready_articles()`，到期自动触发。

**sedimentation → sedimentation**：`extend_sink()`，只延长天数。

**published → published**：无新 commit 时稳态。公开可读、可 fork。

**published → sedimentation**：任意 commit（edit / merge / rollback）后自动 3 天沉淀。

**published → 新 draft**：`fork_article()` 创建 fork。

**不可逆：** published 不能回 draft。sedimentation 不能回 draft（沉淀期作者无写权限）。

## 触发器

`publish_ready_articles` 在以下时机被调用：

| 时机 | 说明 |
|------|------|
| 启动时 | `main()` 入口，dispatch 命令或进入 REPL 之前 |
| CLI `peerpedia scan` | 手动触发 |
| REPL 定时 | 每次命令循环后，距上次扫描 >1 小时 |
| sync 后 | `apply_sync_bundle` 末尾 |

## 数据流

### 本地发布评审

```
CLI: peerpedia review submit abc123 --scores ... --user bob

cli/handlers/reviews.py:
  1. _resolve_user("bob") → user_id
  2. submit_review(db, article_id, reviewer_id, scores, comment)

commands/reviews.py → submit_review():
  3. _write_review_to_git() → 写 reviews/{id}/scores.json + commit → 返回 commit_hash
  4. upsert_review() → 写 DB Review 缓存
  5. recompute_article_score() → 重新算文章总分
  6. recompute_author_reputation() → 更新作者声誉

cli/__init__.py:
  7. db.commit()
```

### sync 收到评审

```
另一个 peer 推送 git bundle
  ↓
ingest_bundle() → 验证 + fetch 对象到本地 repo
  ↓
apply_sync_bundle():
  1. git merge FETCH_HEAD
  2. rebuild_article_authors()        ← 从 git commits 重建作者列表
  3. git_sync_reviews()               ← 读 reviews/*/scores.json → upsert_review
  4. git_sync_status()                ← 从 commit messages 读状态变更
  5. recompute_article_score()        ← 基于最新 DB 缓存算分
  6. publish_ready_articles()         ← 检查是否有到期文章
```

## Git 仓库结构

每篇文章一个独立 Git 仓库：

```
~/.peerpedia/articles/{article_id}/
├── .git/
├── .gitignore                     # 白名单策略
├── article.md                     # 正文 + YAML frontmatter（title, abstract, keywords…）
└── reviews/
    ├── {reviewer_id}/             # 或 sedimentation 阶段的匿名 hash
    │   ├── scores.json            # 五维评分（JSON）
    │   └── threads/
    │       ├── 001.md             # 评审意见
    │       ├── 002.md             # 作者回复
    │       └── ...
    └── ...
```

## 数据目录

```
~/.peerpedia/
├── peerpedia.db          ← SQLite（元数据、评分缓存、作者列表）
├── pending_ops.json      ← 离线操作队列
└── articles/
    └── {article_id}/
```

## 设计规则（写代码时遵守）

1. **Git 存内容，DB 存缓存**——评分缓存从 Git 重新计算，不独立编造
2. **Git-first，DB 后写**——内容先落 Git，成功后写 DB。Git 失败 → DB 不写
3. **workflow/ 是纯计算**——不 import `storage/`、不 import `Session`
4. **入口负责 commit**——crud 只调 `flush()`，CLI/REPL 调 `commit()`
5. **Fail fast**——无 Git → 报错。参数不该为 None → 抛异常。不静默降级
6. **评审是文件夹**——`scores.json` + `threads/`，每个评论独立文件
7. **published 之后的任何 commit 自动触发 3 天沉淀**
