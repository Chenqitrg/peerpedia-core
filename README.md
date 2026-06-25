# PeerPedia Core

同行评审基础设施 — 命令行工具 + Python 库，用于写论文、互相评审、公开发布。

**Git 存内容，数据库存状态。** 每篇文章是一个独立的 Git 仓库 — 正文和评审有完整历史、可 diff/fork/merge；元数据（状态、评分、关系）通过 SQLite 查询和聚合。

[![Tests](https://github.com/Chenqitrg/peerpedia-core/actions/workflows/test.yml/badge.svg)](https://github.com/Chenqitrg/peerpedia-core/actions/workflows/test.yml)
570 tests | 69% coverage | Python 3.11+

## 安装

```bash
pip install peerpedia-core
```

依赖：Python 3.11+，Git。SQLite 自动创建在 `~/.peerpedia/`。

### Tab 补全

```bash
# zsh（加到 ~/.zshrc）
autoload -U bashcompinit && bashcompinit
eval "$(register-python-argcomplete peerpedia)"
```

## 5 分钟上手

### 1. 注册账号

```bash
peerpedia account register --name "Alice"
# → ✓ Registered Alice (id: eef0e359)
```

所有数据存本地 `~/.peerpedia/peerpedia.db`。不需要服务器。密钥由密码 + scrypt 派生，可跨设备恢复。

### 2. 写文章

```bash
peerpedia article create --title "A Note on Tensor Networks" --content "# Intro\n\n..."
```

不传 `--content` 打开 `$EDITOR`。

### 3. 发布到沉淀池

```bash
peerpedia article publish <id> --scores "originality=4,rigor=3,completeness=4,pedagogy=3,impact=4"
```

沉淀池（sedimentation）是 PeerPedia 的评审机制：文章进入限时公开评审期（首次 7 天），到期自动发布。

### 4. 评审

```bash
peerpedia review submit <id> --scores "originality=5,rigor=4,completeness=3,pedagogy=4,impact=5" --comment "Well-structured."
```

作者可以回复评审：

```bash
peerpedia review reply <id> --to @reviewer
```

### 5. Fork & Merge

```bash
peerpedia fork <id>                 # Fork 已发表文章
# 编辑 fork...
peerpedia merge propose <fork-id> --target <original-id>
peerpedia merge accept <proposal-id> --target <article-id>
```

### 6. 多设备

```bash
# 设备 A：导出身份
peerpedia account whoami --verbose --json
# → {"user_id":"...","name":"Alice","public_key":"...","salt":"..."}

# 设备 B：导入并恢复
peerpedia account bootstrap --from '<json>'
peerpedia account recover --user-id <id>
```

### 7. Diff 历史版本

```bash
peerpedia article diff <id> HEAD ~1    # 最近一次修改的 diff
peerpedia article diff <id> <hash1> <hash2>
```

## 状态机

```
draft ──publish()──► sedimentation ──到期自动──► published
                          ▲                          │
                          │   edit / merge           │
                          └──────────────────────────┘
                              (自动 3 天沉淀)
```

## 命令参考

### account — 账户管理

| 命令 | 说明 |
|------|------|
| `account register --name <name>` | 注册新用户 |
| `account login --name <name>` | 登录 |
| `account recover [--name <n>\|--user-id <id>]` | 从密码恢复密钥 |
| `account bootstrap --from '<json>' [--peer <url>]` | 新设备导入身份 |
| `account whoami [--verbose]` | 显示当前用户（--verbose 显示公钥和 salt） |
| `account search <query>` | 搜索用户 |

### article — 文章管理

| 命令 | 说明 |
|------|------|
| `article create --title <t> [--content <c>] [--no-editor]` | 创建草稿 |
| `article create ... --publish --scores <s>` | 创建并直接发布 |
| `article show <id> [--show meta\|full]` | 查看文章 |
| `article list [--status <s>] [--mine] [--feed] [--bookmarked]` | 列出文章 |
| `article list --user <id> [--server <url>]` | 查看远程用户的文章 |
| `article edit <id> [--content <c>] [--title <t>]` | 编辑文章 |
| `article publish <id> --scores <s>` | 发布到沉淀池 |
| `article delete <id>` | 删除草稿 |
| `article diff <id> <hash1> <hash2>` | Diff 两个版本 |
| `article scan` | 触发自动发布 |

### review — 评审

| 命令 | 说明 |
|------|------|
| `review submit <id> --scores <s> [--comment <c>]` | 提交评审 |
| `review list <id> [--show meta\|full]` | 列出评审（full 显示 threads） |
| `review reply <id> --to <reviewer>` | 回复评审（双向对话） |

### maintainer — 合著管理

| 命令 | 说明 |
|------|------|
| `maintainer add <id> --target-user <uid>` | 添加合著者 |
| `maintainer remove <id> --target-user <uid>` | 移除合著者 |
| `maintainer list <id>` | 列出合著者 |
| `maintainer consent <id>` | 同意发布/合并（多作者一致同意） |
| `maintainer revoke <id>` | 撤销同意 |

### notifications — 通知

| 命令 | 说明 |
|------|------|
| `notifications [--all]` | 查看通知（默认未读） |
| `notifications read <id>` | 标记已读 |

### social — 社交

| 命令 | 说明 |
|------|------|
| `follow <user>` | 关注用户 |
| `unfollow <user>` | 取消关注 |
| `following --user <id> [--server <url>]` | 查看关注列表 |
| `followers --user <id> [--server <url>]` | 查看粉丝列表 |
| `bookmark add <id>` | 收藏文章 |
| `bookmark remove <id>` | 取消收藏 |
| `share add <id> [--to <user>] [--comment <c>]` | 分享文章 |
| `share list [--mine]` | 列出分享 |
| `share remove <id>` | 取消分享 |
| `alias set <user> <alias>` | 设置别名 |
| `alias remove <user>` | 删除别名 |
| `alias list` | 列出别名 |

### merge / fork

| 命令 | 说明 |
|------|------|
| `fork <id>` | Fork 已发表文章 |
| `merge propose <fork-id> --target <target-id>` | 提合并请求 |
| `merge accept <proposal-id> --target <id>` | 接受合并 |
| `merge withdraw <proposal-id>` | 撤回合并请求 |

### sync — 同步

| 命令 | 说明 |
|------|------|
| `sync status [--server <url>]` | 查看同步状态 |
| `sync push [--server <url>]` | 推送离线操作 |
| `sync pull [--server <url>]` | 拉取文章更新 |

### 其他

| 命令 | 说明 |
|------|------|
| `compile <id> [--format pdf\|svg\|png\|html]` | 编译文章 |
| `server start [--host <h>] [--port <p>]` | 启动 HTTP 服务器 |

### 通用选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 输出 |
| `--version` | 显示版本 |

## 评分维度

| 维度 | 含义 |
|------|------|
| originality（原创性） | 想法有多新颖 |
| rigor（严谨性） | 论证有多严密 |
| completeness（完整性） | 工作有多完整 |
| pedagogy（教学性） | 写得有多清楚 |
| impact（影响力） | 有多大潜在影响 |

## 通知事件

评审提交、合并提议、新关注者、文章发布、评审回复——这些事件都会产生本地通知，通过 `peerpedia notifications` 查看。

## 架构

```
cli/ + repl.py          ← 入口层：解析参数 → 调编排函数 → commit()
    │
commands/               ← 编排层：唯一同时接触 git 和 db
    │
    ├── storage/        ← git_backend（内容）+ db（元数据），互不知晓
    ├── workflow/       ← 纯计算：评分、声誉、沉淀逻辑
    ├── policies/       ← 权限检查
    ├── bundle/         ← P2P 同步：git bundle 协议
    ├── transport/      ← HTTP 客户端 + 服务器
    └── social/         ← 社交图谱交换
```

## 数据目录

```
~/.peerpedia/
├── peerpedia.db          ← SQLite（元数据、通知、关系）
├── session.json          ← 当前会话（私钥，chmod 600）
├── pending_ops.json      ← 离线操作队列
└── articles/
    └── {article_id}/
        ├── .git/          ← Git 仓库
        ├── article.md     ← 正文
        └── reviews/
            └── {reviewer}/
                ├── scores.json
                └── threads/
                    ├── 001.md
                    ├── 002.md   ← 作者回复 [reply]
                    └── ...
```

## 作为 Python 库使用

```python
from peerpedia_core.commands import (
    create_article_with_content, publish_article, submit_review,
    submit_reply, create_user_stub, create_notification,
)
```

## 开发

```bash
git clone https://github.com/Chenqitrg/peerpedia-core.git
cd peerpedia-core
pip install -e ".[dev]"
pytest tests/ -v
```

## 许可证

CC BY-NC-SA 4.0 with Anti-AI Training Addendum. See [LICENSE](LICENSE).
Copyright (c) 2024-2026 Chenqi Meng and PeerPedia contributors.
