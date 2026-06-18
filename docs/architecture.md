# PeerPedia Core Architecture

## Data Flow

```
CLI (cli.py)
  │  argparse → _resolve_user() → _get_db()
  ▼
commands.py                              sync/
  │  fork_article()                       │  bundle_sync.push()
  │  rollback_article()                  │  bundle_sync.pull()
  │  create_article_with_content()       │  pending_queue.add/flush
  │  update_article_content()            │  network.is_online()
  │  submit_review()
  │  accept_merge()
  │
  ├── policies/articles.py  ← 权限检查
  ├── storage/db/crud_*.py  ← DB 读写 (SQLAlchemy → SQLite)
  └── storage/git_backend   ← Git 操作 (gitpython → ~/.peerpedia/articles/{id}/)
```

## Storage

```
~/.peerpedia/
├── peerpedia.db            ← SQLite (users, articles, reviews, bookmarks, ...)
├── pending_ops.json        ← 离线操作队列
└── articles/
    └── {article_id}/
        ├── .git/            ← 独立 Git 仓库
        ├── article.md       ← Markdown 正文
        ├── article.typ      ← Typst 正文（二选一）
        └── reviews/
            └── {reviewer_id}/
                ├── scores.json
                └── thread.md
```

## Component Map

```
peerpedia_core/
├── cli.py                    argparse + Rich, ~430 lines
├── storage/
│   ├── commands.py           编排函数 (fork, rollback, create, update, review, merge)
│   ├── db/                   ORM models + CRUD + engine
│   ├── git_backend.py        Git 原语 (init, commit, history, bundle, merge)
│   └── compiler.py           Typst/Markdown 编译
├── sync/
│   ├── bundle_sync.py        Git bundle push/pull
│   ├── pending_queue.py      离线队列 (JSON file)
│   └── network.py            网络检测
├── workflow/                 scoring, sedimentation, reputation
├── policies/                 权限规则
├── config/params.py          可调参数
├── exceptions.py             Domain exceptions
└── types/                    数据类型
```

## Article State Machine

```
draft ──publish──► sedimentation ──timeout──► published
  │                    │                          │
  │   edit → draft     │   extend sink            │   fork
  │                    │   review                 │   merge
  └── delete           └── auto-publish           └── delete
```
