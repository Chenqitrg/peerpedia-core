# PeerPedia Core

同行评审基础设施。自包含的命令行工具 + Python 库，用来写论文、互相评审、公开发布。

**Git 存内容，数据库存状态。** 每篇文章是一个独立的 Git 仓库——正文和评审有完整历史、可 diff/fork/merge；元数据（状态、评分）通过 SQLite 查询和聚合。

支持三种写作格式：

| 格式 | 编译方式 | 安装 |
|------|---------|------|
| Markdown | 内建（Python markdown 库） | 零依赖 |
| bTeX | 外部服务器（TypeScript） | `git clone` + `yarn start` |
| Typst | 外部 CLI（Rust） | `brew install typst` |

## 安装

```bash
pip install peerpedia-core
```

依赖：Python 3.11+，Git。SQLite 自动创建在 `~/.peerpedia/`。

### Tab 补全

```bash
# bash（加到 ~/.bashrc）
eval "$(register-python-argcomplete peerpedia)"

# zsh（加到 ~/.zshrc）
autoload -U bashcompinit && bashcompinit
eval "$(register-python-argcomplete peerpedia)"
```

## 5 分钟上手

### 1. 注册账号

```bash
peerpedia account register --name "Alice"
# → ✓ Registered alice (id: eef0e359)

peerpedia account register --name "Bob"
# → ✓ Registered bob (id: 05539e04)
```

所有数据存本地 `~/.peerpedia/peerpedia.db`。不需要服务器。

### 2. 写一篇文章

```bash
peerpedia article create \
    --title "A Note on Tensor Networks" \
    --format markdown \
    --content "# Introduction\n\nTensor networks provide a powerful framework..."
    --user Alice
```

不传 `--content` 会打开 `$EDITOR`。

### 3. 查看文章

```bash
peerpedia article list
# ┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
# ┃ ID       ┃ Title                     ┃ Status ┃
# ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
# │ d7aa1643 │ A Note on Tensor Networks │ draft  │
# └──────────┴───────────────────────────┴────────┘

peerpedia article show d7aa1643
```

### 4. 修改内容

```bash
peerpedia article edit d7aa1643 \
    --content "# Introduction\n\nUpdated version with new results." \
    --user Alice
```

每次修改产生一个新的 Git commit。

### 5. 发布到沉淀池

沉淀池（sedimentation pool）是 PeerPedia 的评审机制：文章进入限时公开评审期（首次 7 天），到期自动发布。

```bash
peerpedia article publish d7aa1643 \
    --scores "originality=4,rigor=3,completeness=4,pedagogy=3,impact=4" \
    --user Alice
```

只能从 draft 发布。已发表文章修改后会自动进入 3 天沉淀期。

### 6. 评审别人的文章

```bash
peerpedia review submit d7aa1643 \
    --scores "originality=5,rigor=4,completeness=3,pedagogy=4,impact=5" \
    --comment "Well-structured argument. Section 3 could use more lemmas." \
    --user Bob
```

### 7. Fork 和 Merge

```bash
peerpedia fork abc123 --user Bob
# → Forked → def456

peerpedia article edit def456 --content "# My improved version" --user Bob

peerpedia merge propose def456 --target abc123 --user Bob
peerpedia merge accept <proposal-id> --target abc123 --user Alice
```

### 8. 自动发布

```bash
# 手动触发
peerpedia article scan
# → 已发布 2 篇文章

# 系统会在启动时、REPL 中、sync 后自动扫描
```

## 状态机

```
draft ──publish()──► sedimentation ──到期自动──► published
                          ▲                          │
                          │   edit / merge / rollback │
                          └──────────────────────────┘
                              (自动 3 天沉淀)
```

- **draft**：草稿，仅作者可见、可编辑
- **sedimentation**：沉淀池，公开可读、可评审、不可编辑
- **published**：公开发表，可 fork。有新 commit 则自动回到 sedimentation

不可撤稿——published 不能回 draft。但可以 edit 修改内容（会自动触发 3 天沉淀）。

## 命令参考

### account

| 命令 | 说明 |
|------|------|
| `account register --name <name>` | 注册新用户 |
| `account whoami` | 显示当前用户 |

### article

| 命令 | 说明 |
|------|------|
| `article create --title <t> --format <md\|typst> [--content <c>] [--user <u>]` | 创建草稿 |
| `article create ... --publish --scores <s>` | 创建并直接发布 |
| `article show <id>` | 查看文章内容 |
| `article edit <id> --content <c> --user <u>` | 编辑文章（published 文章自动进入 3 天沉淀） |
| `article list [--status <draft\|sedimentation\|published>]` | 列出文章 |
| `article publish <id> --scores <s> --user <u>` | 发布到沉淀池（仅 draft） |
| `article delete <id> --force --user <u>` | 删除文章 |
| `article scan` | 手动触发自动发布 |

### review

| 命令 | 说明 |
|------|------|
| `review submit <article-id> --scores <s> [--comment <c>] --user <u>` | 提交评审 |
| `review list <article-id>` | 列出评审 |

### fork / merge

| 命令 | 说明 |
|------|------|
| `fork <article-id> --user <u>` | Fork 已发表文章 |
| `merge propose <fork-id> --target <original-id> --user <u>` | 提合并请求 |
| `merge accept <proposal-id> --target <article-id> --user <u>` | 接受合并 |

### bookmark / compile / sync

| 命令 | 说明 |
|------|------|
| `bookmark add <article-id> --user <u>` | 添加书签 |
| `bookmark list --user <u>` | 列出书签 |
| `compile <id> [--format pdf\|svg\|png\|html]` | 编译文章 |
| `sync status` | 查看同步状态 |
| `sync push` | 推送 pending 操作 |

### 通用选项

| 选项 | 说明 |
|------|------|
| `--json` | 输出 JSON |
| `--user <name\|id>` | 以指定用户身份操作 |

## 评分维度

| 维度 | 含义 |
|------|------|
| originality（原创性） | 想法有多新颖 |
| rigor（严谨性） | 论证有多严密 |
| completeness（完整性） | 工作有多完整 |
| pedagogy（教学性） | 写得有多清楚 |
| impact（影响力） | 有多大潜在影响 |

## 数据目录

```
~/.peerpedia/
├── peerpedia.db          ← SQLite（元数据、评分缓存、作者列表）
├── pending_ops.json      ← 离线操作队列
└── articles/
    └── {article_id}/
        ├── .git/          ← Git 仓库
        ├── article.md     ← 正文 + YAML frontmatter
        └── reviews/
            └── {reviewer}/scores.json + threads/*.md
```

## 作为 Python 库使用

```python
from peerpedia_core.commands import (
    create_article_with_content,
    publish_article,
    submit_review,
    publish_ready_articles,
)
from peerpedia_core.storage.db.engine import get_engine, get_session, init_db

engine = get_engine("sqlite:///my_peerpedia.db")
init_db(engine)
db = get_session(engine)

result = create_article_with_content(
    db, title="My Paper", content="# Hello", format="markdown", author_ids=["alice"],
)
db.commit()
```

## 开发

```bash
git clone https://github.com/Chenqitrg/peerpedia-core.git
cd peerpedia-core
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

架构详见 [docs/architecture.md](docs/architecture.md)。

## 许可证

CC BY-NC-SA 4.0 with Anti-AI Training Addendum. See [LICENSE](LICENSE).

Copyright (c) 2024-2026 Chenqi Meng and PeerPedia contributors.
