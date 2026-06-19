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
- **Git 是内容 SOT**——正文和评审内容存在 Git 仓库中，DB 只存评分缓存
- commands.py 不主动 commit 事务，由调用方（CLI）commit
- 模块间不跨调——sync 不直接查 DB，workflow 不直接调 Git
- **Git 层与 DB 层互相不知道对方存在**，只有 commands.py 知道两边的接口

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
| `create_article_with_content()` | Git → DB | 先 init repo + commit 正文和自评，再建 DB 行 |
| `update_article_content()` | Git → DB | 先 commit 新内容，再更新 DB 元数据 |
| `fork_article()` | Git → DB | 先 git clone 原 repo，再从 git 推导作者，最后建 DB 行 |
| `rollback_article()` | Git → DB | 先 checkout 旧版 + commit，再更新 DB |
| `submit_review()` | Git → DB | 评审文件先落 Git（reviews/{id}.md），成功后才写 DB 评分缓存 |
| `accept_merge()` | Git → DB | 先 git merge，再从 git 推导作者，最后更新 DB |

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
| `init_article_repo(repo_path)` | 创建 Git 仓库 + reviews/ 目录 |
| `commit_article(repo_path, message, author_name, author_email)` | 提交工作区改动 |
| `get_commit_history(repo_path)` | 获取提交历史 |
| `get_commit_authors(repo_path)` | 从 git commit email 提取作者列表 |
| `get_diff_between(repo_path, hash1, hash2)` | 两个 commit 之间的 diff |
| `create_bundle(repo_path, since_hash)` | 创建增量 bundle |
| `apply_bundle(repo_path, bundle_bytes)` | 应用远程 bundle |
| `merge_git_repos(target, fork, author_name)` | Git merge fork 到 target |
| `delete_article_repo(repo_path)` | 删除文章 Git 仓库 |

### 权限 (policies/articles.py)

| 函数 | 检查内容 |
|------|---------|
| `assert_can_read_article()` | 作者本人 / 公开文章 / 沉淀池文章（认证用户） |
| `assert_can_edit_article()` | 只有作者本人 |
| `assert_can_fork_article()` | 只有 published 状态 |
| `assert_can_publish_article()` | 只有作者本人 |
| `assert_can_download()` | 作者本人 / published |

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
     a. 写 reviews/{reviewer_id}/scores.json
     b. 写 reviews/{reviewer_id}/threads/{nnn}.md
     c. git commit
  6. upsert_review() → 写 DB 评分缓存
  7. compute_article_score() → 重新算文章总分
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

1. **Git 存内容，DB 存缓存** — Git 仓库存正文 + 评审文件（SOT），DB 存评分缓存 + 元数据（status、fork_count）。评分缓存从 Git 重新计算，不独立编造
2. **Git-first，DB 后写** — 所有内容先落 Git（commit），成功后才写 DB。Git 失败 → DB 不写
3. **Git 与 DB 互不知晓** — 两个存储层不互相 import，只有 commands.py 知道两者
4. **Fail fast** — 无 Git → 报错，不静默降级
5. **编排函数不 commit** — commands.py 只做 add/flush，CLI 调 db.commit()
6. **评审是文件夹，评分和评论分离** — `reviews/{id}/scores.json` + `threads/` 子目录，每个评论是独立文件
7. **自评即评审** — 作者自评存在 `reviews/{author_id}/`，和其他评审同格式同流程
