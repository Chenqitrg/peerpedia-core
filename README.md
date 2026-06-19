# PeerPedia Core

同行评审基础设施。一个自包含的命令行工具 + Python 库，用来写论文、互相评审、公开发布。

**Git 存内容，数据库存状态。** 每篇文章是一个独立的 Git 仓库——正文和评审内容有完整历史、可 diff/fork/merge；元数据（状态、评分、fork 计数）通过 SQLite 查询和聚合。

支持三种写作格式：

| 格式 | 编译方式 | 安装 |
|------|---------|------|
| Markdown | 内建（Python markdown 库） | 零依赖，开箱即用 |
| bTeX | 外部服务器（TypeScript） | `git clone` + `yarn start`，~2MB |
| Typst | 外部 CLI（Rust） | `brew install typst`，~30MB |

## 安装

```bash
pip install peerpedia-core
```

依赖：Python 3.11+，Git。不需要数据库服务——SQLite 文件自动创建在 `~/.peerpedia/`。

### 启用 Tab 补全

```bash
# bash（加到 ~/.bashrc）
eval "$(register-python-argcomplete peerpedia)"

# zsh（加到 ~/.zshrc）
autoload -U bashcompinit && bashcompinit
eval "$(register-python-argcomplete peerpedia)"
```

然后就可以 `peerpedia <TAB>` 看到所有子命令，`peerpedia article <TAB>` 看到 create/edit/show 等。

## 5 分钟上手

### 1. 注册账号

```bash
peerpedia account register --name "Alice"
# → ✓ Registered alice (id: eef0e359)

peerpedia account register --name "Bob"
# → ✓ Registered bob (id: 05539e04)
```

所有数据存在本地的 `~/.peerpedia/peerpedia.db`。不需要连服务器。

### 2. 写一篇文章

```bash
peerpedia article create \
    --title "A Note on Tensor Networks" \
    --format markdown \
    --content "# Introduction\n\nTensor networks provide a powerful framework..."
    --user Alice
```

`--format` 可以是 `markdown`、`btex` 或 `typst`。不传 `--content` 的话会打开 `$EDITOR` 让你写。

### 3. 看看写了什么

```bash
peerpedia article list
# ┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
# ┃ ID       ┃ Title                     ┃ Status ┃
# ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
# │ d7aa1643 │ A Note on Tensor Networks │ draft  │
# └──────────┴───────────────────────────┴────────┘

peerpedia article show d7aa1643
# ╭─ Article ───────────────────────────────╮
# │  A Note on Tensor Networks      draft   │
# │  Authors: alice                         │
# │  ...                                    │
# ╰─────────────────────────────────────────╯
```

### 4. 修改内容

```bash
peerpedia article edit d7aa1643 \
    --content "# Introduction\n\nUpdated version with new results." \
    --user Alice
# → ✓ Updated d7aa1643 — A Note on Tensor Networks
```

每次修改都会在 Git 里产生一个新的 commit。

### 5. 发布到沉淀池

沉淀池（sedimentation pool）是 PeerPedia 的评审机制：你提交自评后，文章进入一个限时的公开评审期，别人可以来评审。

```bash
peerpedia article publish d7aa1643 \
    --scores "originality=4,rigor=3,completeness=4,pedagogy=3,impact=4" \
    --user Alice
# → ✓ Published d7aa1643 to sedimentation pool
#     originality    ★★★★☆  4/5
#     rigor          ★★★☆☆  3/5
#     ...
```

也可以创建时直接发布：

```bash
peerpedia article create --title "My Paper" \
    --format markdown --content "# Hello" \
    --user Alice --publish \
    --scores "originality=4,rigor=3,completeness=4,pedagogy=3,impact=4"
```

### 6. 评审别人的文章

```bash
peerpedia review submit d7aa1643 \
    --scores "originality=5,rigor=4,completeness=3,pedagogy=4,impact=5" \
    --comment "Well-structured argument. Section 3 could use more lemmas." \
    --user Bob
# → ✓ Review submitted

peerpedia review list d7aa1643
# → 显示所有评审的评分
```

### 7. Fork 和 Merge

Fork 一篇已发表的文章，改你自己的版本，然后提 Merge 请求：

```bash
peerpedia fork abc123 --user Bob
# → ✓ Forked → def456

# 编辑你的 fork...
peerpedia article edit def456 --content "# My improved version" --user Bob

# 提合并请求
peerpedia merge propose def456 --target abc123 --user Bob
# → ✓ Merge proposed

# 原作者接受
peerpedia merge accept <proposal-id> --target abc123 --user Alice
# → ✓ Merge accepted
```

### 8. 书签

```bash
peerpedia bookmark add abc123 --user Bob
# → ✓ Bookmarked abc123

peerpedia bookmark list --user Bob
# → 列出所有书签
```

### 9. 离线同步

```bash
# 查看同步状态
peerpedia sync status
# ╭─ Sync Status ───────────────────────╮
# │  Server:  offline                   │
# │  Pending: 3 ops                     │
# ╰─────────────────────────────────────╯

# 联网后推送
peerpedia sync push
# → ✓ Pushed 2 articles, deleted 1
```

设置服务器地址：
```bash
export PEERPEDIA_SERVER="https://peerpedia.example.com"
```

## 命令参考

### account

| 命令 | 说明 |
|------|------|
| `account register --name <name>` | 注册新用户 |
| `account whoami` | 显示当前用户 |

### article

| 命令 | 说明 |
|------|------|
| `article create --title <t> --format <md\|typst> [--content <c>] [--user <u>]` | 创建文章。不传 --content 会打开 $EDITOR |
| `article create ... --publish --scores <s>` | 创建并直接发布到沉淀池 |
| `article show <id> [--user <u>]` | 查看文章内容和元数据 |
| `article edit <id> --content <c> [--title <t>] --user <u>` | 编辑文章，产生新 commit |
| `article list [--status <draft\|sedimentation\|published>]` | 列出文章 |
| `article publish <id> --scores <s> --user <u>` | 发布到沉淀池 |
| `article delete <id> --force --user <u>` | 删除文章（仅 draft 和 published） |

### review

| 命令 | 说明 |
|------|------|
| `review submit <article-id> --scores <s> [--comment <c>] --user <u>` | 提交评审 |
| `review list <article-id>` | 列出文章的所有评审 |

### fork / merge

| 命令 | 说明 |
|------|------|
| `fork <article-id> --user <u>` | Fork 一篇已发表的文章 |
| `merge propose <fork-id> --target <original-id> --user <u>` | 提合并请求 |
| `merge accept <proposal-id> --target <article-id> --user <u>` | 接受合并 |

### bookmark

| 命令 | 说明 |
|------|------|
| `bookmark add <article-id> --user <u>` | 添加书签 |
| `bookmark list --user <u>` | 列出书签 |

### compile

| 命令 | 说明 |
|------|------|
| `compile <id> [--format pdf\|svg\|png\|html]` | 编译文章 |

### sync

| 命令 | 说明 |
|------|------|
| `sync status` | 查看同步状态（在线/离线、pending 数量） |
| `sync push` | 推送所有 pending 操作 |

### 通用选项

| 选项 | 说明 |
|------|------|
| `--json` | 输出机器可读的 JSON |
| `--user <name\|id>` | 以指定用户身份操作（支持用户名或 UUID） |

## 评分维度

所有评分都是 1-5 分，五个维度：

| 维度 | 英文 | 含义 |
|------|------|------|
| 原创性 | originality | 想法有多新颖 |
| 严谨性 | rigor | 论证有多严密 |
| 完整性 | completeness | 工作有多完整 |
| 教学性 | pedagogy | 写得有多清楚 |
| 影响力 | impact | 有多大的潜在影响 |

## 数据在哪里

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
            ├── {reviewer_a}.md   ← 评审人的评审 + 作者回复（Markdown 对话线程）
            ├── {reviewer_b}.md
            └── {author}.md      ← 作者自评（和其他评审同格式）
```

备份只需要复制整个 `~/.peerpedia/` 目录。迁移到新机器：复制目录 + 安装 peerpedia-core。

## 作为 Python 库使用

```python
from peerpedia_core.storage.commands import create_article_with_content, fork_article
from peerpedia_core.storage.db.engine import get_engine, get_session, init_db

engine = get_engine("sqlite:///my_peerpedia.db")
init_db(engine)
db = get_session(engine)

# 创建文章
result = create_article_with_content(
    db, title="My Paper", content="# Hello", format="markdown", user_id="alice",
)
db.commit()
print(result["id"])
```

## 参与开发

环境搭建、Review 顺序、测试指南、VS Code 配置见 [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)。
架构设计见 [docs/architecture.md](docs/architecture.md)。

```bash
git clone https://github.com/Chenqitrg/peerpedia-core.git
cd peerpedia-core
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

## 许可证

CC BY-NC-SA 4.0 with Anti-AI Training Addendum. See [LICENSE](LICENSE).

Copyright (c) 2024-2026 Chenqi Meng and PeerPedia contributors.
