# PeerPedia Core — Architecture

## 文件树

```
peerpedia_core/
├── __init__.py
├── cli.py                    # 命令行入口（argparse + Rich）
├── repl.py                   # 交互式 REPL（prompt_toolkit）
├── commands.py               # 业务编排层（create_article_with_content、fork_article、submit_review...）
├── compiler.py               # 编译后端（Markdown→HTML、Typst→PDF/SVG/PNG）
├── exceptions.py             # 自定义异常（NotFound, NotAuthorized, Conflict...）
│
├── config/
│   └── params.py             # 全局可调参数（沉淀天数、评分权重、评论长度限制）
│
├── policies/
│   └── articles.py           # 权限检查（谁能读/写/fork/publish/下载）
│
├── storage/
│   ├── git_backend.py        # Git 操作（init、commit、history、diff、blame、bundle）
│   └── db/
│       ├── engine.py         # SQLAlchemy 引擎 + init_db + migrate
│       ├── models.py         # ORM 模型（Article、User、Review、Follow、Bookmark...）
│       ├── session_utils.py  # 事务装饰器（commit/rollback/session 生命周期）
│       ├── crud_article.py   # Article CRUD
│       ├── crud_user.py      # User + Follow CRUD
│       ├── crud_review.py    # Review CRUD
│       ├── crud_bookmark.py  # Bookmark CRUD
│       ├── crud_merge.py     # MergeProposal CRUD
│       └── crud_citation.py  # Citation CRUD
│
├── sync/
│   ├── network.py            # 网络检测（is_online）
│   ├── bundle_sync.py        # Git bundle 同步（create_bundle、apply_bundle）
│   └── pending_queue.py      # 离线操作队列（add、list、remove、count）
│
├── workflow/
│   ├── scoring.py            # 评分聚合（compute_article_score、加权平均）
│   ├── sedimentation.py      # 沉淀池（is_ready_to_publish、publish_ready_articles）
│   └── reputation.py         # 声誉计算（compute_author_reputation）
│
└── types/
    ├── scores.py             # 五维评分类型（FiveDimScores）
    └── messages.py           # Thread 消息类型

tests/
├── conftest.py               # 共享 fixture（临时 SQLite 引擎）
├── conftest_backend.py       # [死代码] 引用不存在的 peerpedia_api
├── e2e.sh                    # 端到端黑盒测试（CLI 命令 + 断言）
├── test_commands.py          # 编排层测试（fork、rollback、create、update）
├── test_crud.py              # DB CRUD 测试（Article、Review、User、Follow、Bookmark...）
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
├── test_exceptions.py        # 异常类测试
└── test_seed.py              # 种子数据验证
```

## 分层架构

```
┌──────────────────────────────────────────────┐
│  cli.py / repl.py        用户界面层          │
│  argparse + Rich 美化输出                     │
│  职责：解析参数、格式化输出、--json 支持      │
└──────────────────┬───────────────────────────┘
                   │ 只调 commands.py 和 crud_*.py
┌──────────────────▼───────────────────────────┐
│  commands.py             业务编排层          │
│  fork_article()                              │
│  create_article_with_content()               │
│  submit_review()                             │
│  职责：把多个原语串成业务操作                  │
└────┬──────────┬──────────┬───────────────────┘
     │          │          │
┌────▼────┐ ┌───▼────┐ ┌──▼──────────────┐
│policies/│ │storage/│ │storage/         │
│articles │ │db/     │ │git_backend      │
│         │ │        │ │                 │
│权限检查  │ │SQLite  │ │Git 仓库操作      │
│         │ │增删改查 │ │init/commit/diff │
└─────────┘ └────────┘ └─────────────────┘
```

**规则：**
- CLI 不直接碰 Git，通过 commands.py
- 正文和评审内容写 Git，元数据写 DB（state 优先查询走 DB）
- commands.py 不主动 commit 事务，由调用方（CLI）commit
- 模块间不跨调——sync 不直接查 DB，workflow 不直接调 Git

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
| `Review` | reviews | article_id, reviewer_id, scope(self/pool), commit_hash, scores(JSON), thread(JSON) |
| `Follow` | follows | follower_id, followed_id (联合唯一) |
| `Bookmark` | bookmarks | user_id, article_id (联合唯一) |
| `MergeProposal` | merge_proposals | fork_article_id, target_article_id, status(pending/accepted/rejected) |
| `Citation` | citations | source_article_id, cited_article_id, probabilities(JSON) |

## 关键函数

### 编排层 (commands.py，顶层)

| 函数 | 写入顺序 | 说明 |
|------|---------|------|
| `create_article_with_content()` | DB → Git → DB | 先建 DB 行获得 ID，再 init repo + commit 正文 |
| `update_article_content()` | DB → Git → DB | 先验证权限，写文件 commit 后更新 DB 元数据 |
| `fork_article()` | DB验证 → copy repo → DB | 先验证原文章，再 copy repo，最后建 DB 行 |
| `rollback_article()` | Git → DB | 先建 revert commit，再更新 DB |
| `submit_review()` | Git → DB | **唯一 git-first**：评审文件先落 Git，成功后才写 DB |
| `accept_merge()` | DB → Git → DB | 先验证权限，再 merge git，最后更新 DB |

### DB CRUD (storage/db/)

| 文件 | 关键函数 |
|------|---------|
| `crud_article.py` | `create_article`, `get_article`, `list_articles`, `update_article_status`, `delete_article` |
| `crud_user.py` | `create_user`, `get_user`, `get_user_by_username`, `follow_user`, `unfollow_user`, `get_followers`, `get_following`, `get_follower_count` |
| `crud_review.py` | `create_review`, `get_reviews_for_article`, `update_review_scores`, `upsert_review` |
| `crud_bookmark.py` | `add_bookmark`, `remove_bookmark`, `get_bookmarks_for_user`, `is_bookmarked` |
| `crud_merge.py` | `create_merge_proposal`, `accept_merge_proposal` |
| `crud_citation.py` | `create_citation`, `update_citation_probabilities` |

### Git 操作 (git_backend.py)

| 函数 | 职责 |
|------|------|
| `init_article_repo(article_id, base_dir)` | 创建裸 Git 仓库 + article.md |
| `commit_article(repo, message, author, email)` | 提交工作区改动 |
| `get_commit_history(repo)` | 获取提交历史 |
| `get_diff_between(repo, hash_a, hash_b)` | 两个 commit 之间的 diff |
| `create_bundle(repo, since_hash)` | 创建增量 bundle |
| `apply_bundle(repo, bundle_path)` | 应用远程 bundle |

### 权限 (policies/articles.py)

| 函数 | 检查内容 |
|------|---------|
| `assert_can_read_article()` | 作者本人 / 公开文章 / 沉淀池文章（认证用户） |
| `assert_can_edit_article()` | 只有作者本人 |
| `assert_can_fork_article()` | 只有 published 状态 |
| `assert_can_publish_article()` | 只有作者本人 |
| `assert_can_download()` | 作者本人 / published |

## 数据流：一个评审的完整路径

```
用户敲: peerpedia review submit abc123 --scores ... --user feynman

cli.py:
  1. _resolve_user("feynman") → user_id
  2. 调用 submit_review(db, "abc123", user_id, scores, ...)

commands.py → submit_review():
  3. get_user(db, reviewer_id) → 确认评审人存在
  4. get_article(db, article_id) → 确认文章存在
  5. _write_review_to_git():
     a. 检查 .git/ 是否存在（无 → 报错，fail-fast）
     b. 写 reviews/{reviewer_id}/scores.json
     c. 写 reviews/{reviewer_id}/thread.md
     d. git commit
  6. create_review() 或 update_review_scores() → 写 DB
  7. compute_article_score_for_commit() → 重新算文章总分
  8. compute_author_reputation() → 更新作者声誉

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

## 设计规则（写代码时遵守）

1. **双存储，各司其职** — Git 存内容（正文、评审文件），DB 存状态（status、score、fork_count）。内容有版本历史，状态可查询聚合。评审内容是 git-first，元数据 DB 先行
2. **Git 不可篡改** — 正文和评审内容一经 git commit 不可修改。DB 中的元数据（score 等）可由 workflow 重算更新
3. **Fail fast** — 无 Git → 报错，不静默降级
4. **编排函数不 commit** — commands.py 只做 add/flush，CLI 调 db.commit()
5. **模块不跨调** — sync 不直接查 DB，workflow 不直接调 Git
6. **`_resolve_user()` 支持 username + UUID** — 所有涉及用户的 CLI 参数都用它
7. **每个 CLI 命令支持 `--json`** — 机器可读输出
8. **空列表用 `[muted]` 提示** — 带引导文案，不是静默空屏
