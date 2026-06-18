# PeerPedia Core — Architecture

写给想要理解这个项目如何工作的开发者。不需要先懂学术出版——只需要懂 Python 和 Git。

## 这个项目解决什么问题

学术出版需要三个东西：**写论文**、**同行评审**、**公开发布**。现有系统（期刊投稿系统、arXiv）把这三件事拆在不同的工具里，而且不透明——你无法看到一篇论文被谁、怎么评审过。

PeerPedia 把这三件事放在一个工具里，用 **Git** 记录所有历史（谁在什么时候写了什么、谁评审了、评审内容是什么），用 **SQLite** 做快速查询。

## 核心设计决策

### 每篇文章是一个独立的 Git 仓库

```
~/.peerpedia/articles/
├── abc123/                  ← 爱因斯坦的相对论论文
│   ├── .git/                ← 完整的 Git 历史
│   ├── article.md           ← 论文正文（Markdown）
│   └── reviews/
│       └── feynman-id/      ← 费曼的评审
│           ├── scores.json   ← {"originality": 5, "rigor": 4, ...}
│           └── thread.md    ← 评审讨论串
├── def456/                  ← 狄拉克的量子电动力学论文
│   └── ...
```

**为什么是 Git？** 因为 Git 天然提供：
- 完整历史（git log → 看到每次修改）
- 不可篡改（改了任何东西 hash 就变了）
- 可以 fork（复制一份，改你自己的版本）
- 可以 merge（把你的改进合并回原文）
- 可以同步（git bundle → 打包发给远程服务器）

### SQLite 是索引，不是真相

```
Git 里的数据（权威）           SQLite 里的数据（缓存/索引）
─────────────────────         ──────────────────────────
文章内容 (article.md)         articles 表（标题、状态、分数）
评审数据 (scores.json)        reviews 表（方便按分数排序）
作者信息 (git commit author)  users 表（登录、关注、书签）
```

规则：**Git 里的数据可以重建 SQLite，反过来不行。** 如果数据库丢了，从 Git 跑一遍就能恢复。

## 代码结构

从调用链的角度看，从上到下：

```
┌─────────────────────────────────────────────────────┐
│  cli.py                    ← 你敲的命令行           │
│  "peerpedia article create --title ..."             │
│  职责：解析参数、显示结果、处理 --json 输出         │
└──────────────────────┬──────────────────────────────┘
                       │ 调用
┌──────────────────────▼──────────────────────────────┐
│  storage/commands.py      ← 业务编排               │
│  fork_article()                                   │
│  create_article_with_content()                     │
│  submit_review()          ← 每个函数把多个原语串起来│
│  职责："fork = 复制仓库 + 创建DB记录 + 重建作者"    │
└──────┬───────────────┬───────────────┬──────────────┘
       │               │               │
┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────────────┐
│ policies/   │ │ storage/db/ │ │ storage/git_backend │
│ 权限检查     │ │ SQLite CRUD │ │ Git 操作             │
│             │ │              │ │                     │
│ "只有发表   │ │ create_      │ │ init_article_repo() │
│  的文章     │ │ article()    │ │ commit_article()    │
│  才能 fork" │ │ get_article()│ │ get_commit_history()│
└─────────────┘ └─────────────┘ └─────────────────────┘
```

### 各模块职责

| 模块 | 文件 | 一句话 |
|------|------|--------|
| CLI | `cli.py` | 命令行入口，argparse 解析 + Rich 美化输出 |
| 编排 | `storage/commands.py` | 把 5 个原语函数串成一个业务操作 |
| 权限 | `policies/articles.py` | "这个用户能做这件事吗？" |
| 数据库 | `storage/db/` | SQLAlchemy ORM，建表、增删改查 |
| Git | `storage/git_backend.py` | 创建仓库、提交、查看历史、bundle 同步 |
| 编译 | `storage/compiler.py` | Markdown/Typst → HTML/PDF |
| 同步 | `sync/` | Git bundle 推送到远程、离线操作队列 |
| 工作流 | `workflow/` | 评分聚合、沉淀池、声誉计算 |
| 配置 | `config/params.py` | 所有可调参数（沉淀天数、评分权重等） |

### 两个重要规则

**1. 编排函数不提交事务**

```python
# commands.py 里的函数只做 session.add() / session.flush()
# 调用方（CLI 或 HTTP route）在末尾调 db.commit()
fork_article(db, article_id, user_id)  # 不 commit
db.commit()  # 调用方 commit
```

**2. Git-first：先写 Git，再写数据库**

提交评审的流程是：
1. 把 scores.json 和 thread.md 写入 Git 仓库
2. git commit
3. 成功后才写 SQLite

如果第 1 步失败（磁盘满了、锁冲突），数据库保持干净——不会出现"数据库说有评审但 Git 里没有"的不一致状态。

## 文章状态机

```
                 publish
  ┌──────┐ ───────────────► ┌──────────────┐
  │draft │                  │sedimentation │  沉淀池：限时接受社区评审
  └──┬───┘                  └──────┬───────┘
     │  edit → 回到 draft          │  timeout → 自动发布
     │  delete                     │  extend → 延长评审期
     ▼                             ▼
   删除                       ┌──────────┐
                              │published │  公开发表，可以 fork
                              └──────────┘
```

- **draft**：作者正在写，只有自己能看到
- **sedimentation**：作者提交了自评，进入沉淀池。别人可以评审。7 天后自动发布
- **published**：公开发表。任何人都可以阅读、fork

## 权限模型

```
谁能做什么             draft   sedimentation   published
─────────────────────────────────────────────────────
作者本人  查看          ✓       ✓               ✓
作者本人  编辑          ✓       ✗               ✓
作者本人  删除          ✓       ✗               ✓
作者本人  自评          ✓       ✓               ✗
任何人   评审          ✗       ✓               ✓
任何人   fork          ✗       ✗               ✓
任何人   书签          ✗       ✗               ✓
```

权限定义在 `policies/articles.py`，前端和 CLI 都调同一套函数。

## 同步协议

```
本地机器                          远程服务器
────────                          ──────────
git bundle create ──────────────► POST /sync (二进制)
  (增量：只包含服务器没有的 commit)
                                  
                                  409 Conflict ←──── 服务器有我们没有的 commit
git bundle pull ◄──────────────── GET /bundle?since=<hash>
git bundle push ────────────────► POST /sync (重试)
                                  ✓ 200
```

离线时：操作写入 `pending_ops.json`，联网后自动 flush。

## 数据流：一个评审的完整路径

```
用户敲命令：
  peerpedia review submit abc123 --scores ... --user feynman

cli.py:
  1. 解析 --scores → {"originality": 5, "rigor": 4, ...}
  2. _resolve_user("feynman") → user_id
  3. 调用 submit_review(db, "abc123", user_id, scores, ...)

commands.py → submit_review():
  4. 权限检查：文章存在？用户存在？可以评审？
  5. Git-first：写 reviews/feynman-id/scores.json + thread.md
  6. git commit
  7. 写 SQLite：create_review() 或 update_review_scores()
  8. 重新计算文章总分：compute_article_score_for_commit()
  9. 更新作者声誉：compute_author_reputation()

cli.py:
  10. db.commit()
  11. 显示结果：✓ Review submitted + 星级评分
```
