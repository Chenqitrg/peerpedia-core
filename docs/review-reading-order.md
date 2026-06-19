# Review 文件阅读顺序

## 总原则

**从外到内，从抽象到具体，从不变到易变。**

先理解架构约束和错误模型，再看数据结构和权限规则，最后看业务逻辑和胶水代码。如果顺序反了——比如先看 `cli.py`——你会被实现细节淹没，看不到整体约束。

---

## 第一遍：建立心智模型（必读，按顺序）

每次 review 一个 PR 之前，至少要对以下文件有印象。如果你已经熟悉代码库，跳到第二遍。

| 序号 | 文件 | 读什么 | 耗时 |
|------|------|--------|------|
| 1 | [architecture.md](architecture.md) | 分层图、数据模型 ER 图、关键函数表、设计规则 1-8 | 10min |
| 2 | [exceptions.py](../peerpedia_core/exceptions.py) | 4 个异常类的语义：`NotFoundError` / `NotAuthorizedError` / `ConflictError` / `BadRequestError` | 2min |
| 3 | [params.py](../peerpedia_core/config/params.py) | `SinkParams` / `ScoreParams` / `ReputationParams` 的默认值 | 3min |
| 4 | [models.py](../peerpedia_core/storage/db/models.py) | 7 个 ORM 类的字段、外键、UniqueConstraint | 8min |
| 5 | [scores.py](../peerpedia_core/types/scores.py) | `FiveDimScores`（5 维）和 `ReputationScores`（4 维）的结构 | 2min |

**第一遍的目标：** 你能回答"文章有几种状态？评分有哪五个维度？权限检查用哪个异常？"

---

## 第二遍：理解核心机制（必读，按顺序）

这一遍覆盖所有"被依赖"的模块——它们是底层，上层代码的正确性取决于它们。

| 序号 | 文件 | 读什么 | 为什么在这里 |
|------|------|--------|-------------|
| 6 | [engine.py](../peerpedia_core/storage/db/engine.py) | Engine 缓存、WAL + foreign_keys pragma、`JSONList`/`JSONDict` 类型 | DB 是所有模块的基础 |
| 7 | [session_utils.py](../peerpedia_core/storage/db/session_utils.py) | `db_session_scope` context manager——理解事务边界 | CLI 和 commands 都依赖它 |
| 8 | [git_backend.py](../peerpedia_core/storage/git_backend.py) | `init_article_repo` / `commit_article` / `get_commit_history` / `get_diff_between` / `get_commit_authors` / `merge_git_repos` / `delete_article_repo` | Git 是第二个存储引擎 |
| 8b | [sync/git_bundle.py](../peerpedia_core/sync/git_bundle.py) | `create_bundle` / `apply_bundle` / `find_common_ancestor` / `is_ancestor` | git bundle 协议——自包含，不依赖 git_backend |
| 8c | [sync/monotonic_search.py](../peerpedia_core/sync/monotonic_search.py) | `search_monotonic_boundary` — k-exponential 搜索 + 二分精确定位 | 纯算法，无外部依赖 |
| 9 | [policies/articles.py](../peerpedia_core/policies/articles.py) | 每个 `assert_can_*` 函数——谁可以读写/fork/publish/download | 权限是业务规则的集中表达 |
| 10 | [crud_article.py](../peerpedia_core/storage/db/crud_article.py) | `create_article` / `get_article` / `list_articles` / `delete_article` / `set_sink_start` / `extend_sink` | 最复杂的 CRUD，其他 CRUD 结构类似 |

**第二遍的目标：** 你能解释"一个 Git commit 和一条 DB 记录的关系是什么？谁会先被创建？"

---

## 第三遍：理解业务编排（按依赖顺序）

`commands.py` 是业务编排层——它把 CRUD + Git + Policy + Workflow 串成完整操作。

| 序号 | 文件 | 读什么 | 关键点 |
|------|------|--------|--------|
| 11 | [scoring.py](../peerpedia_core/workflow/scoring.py) | `compute_article_score` + `compute_article_score_for_commit` | 加权平均逻辑， reviewer 权重 |
| 12 | [reputation.py](../peerpedia_core/workflow/reputation.py) | `compute_author_reputation` + `get_reviewer_weight` | 5 维→4 维的映射，EMA 平滑 |
| 13 | [sedimentation.py](../peerpedia_core/workflow/sedimentation.py) | `publish_ready_articles`——两阶段事务 | draft→published 的自动化 |
| 14 | [commands.py](../peerpedia_core/commands.py) | **所有函数**：`create_article_with_content` / `update_article_content` / `fork_article` / `rollback_article` / `submit_review` / `accept_merge` | 注意每个函数的 **写入顺序**（DB→Git→DB 还是 Git→DB） |

**第三遍的目标：** 你能画出 `submit_review` 从 CLI 参数到最终 score 计算的完整调用链。

---

## 第四遍：理解服务器与本地的关系（必读）

### 一句话回答最常被问的问题

**"服务器和本地安装的是同一套代码吗？"**

是的。`peerpedia-core` 就是唯一的代码库。安装后得到 `peerpedia` 命令：

```
$ pip install peerpedia-core
$ peerpedia article create --title "量子计算综述"   # 本地操作
$ peerpedia sync push --server https://peerpedia.example.com  # 推送到服务器
$ peerpedia serve                                    # 自己就是服务器（未来）
```

没有"客户端版"和"服务器版"两个包——就像 `git` 命令一样，你既可以 `git commit`（本地），也可以 `git push`（联网），还可以 `git daemon`（充当服务器）。peerpedia 的服务器只是一个恰好挂在公网 IP 上、接受 sync 请求的对等节点。

**"storage 里哪些归服务器？哪些归本地？"**

同一套 `models.py`、同一个 `git_backend.py`、同一个 `crud_*.py`。区别不在代码，在**数据目录的内容**：

```
服务器 (~/.peerpedia/)                   本地 (~/.peerpedia/)
├── peerpedia.db                         ├── peerpedia.db
│   ├── articles (所有用户)              │   ├── articles (自己的 + pull 来的)
│   ├── users (所有注册用户)             │   ├── users (自己 + 交互过的人)
│   └── reviews (缓存)                   │   └── reviews (自己的评审缓存)
│                                        │
├── articles/                            ├── articles/
│   ├── <id1>/.git  (全部文章)           │   ├── <id1>/.git  (pull 的子集)
│   ├── <id2>/.git                       │   └── <id3>/.git
│   └── ...                              │
│                                        │
└── 不需要 compiler 缓存                 └── compiler 缓存
```

**核心原则**：代码一样，数据不同。服务器的数据库有所有用户的记录，你的本机只有和自己相关的。

### 类比：科学计算中的"本地 vs 服务器"

如果你来自数学/物理背景，用科学计算的思维来理解：

```
科学计算                                peerpedia
───────                                 ────────
.h5 / .npy 数据文件                      git repo (= 带版本历史的 .h5 文件)

ssh 到集群跑 julia simulation           peerpedia serve (= 启动一个接受 sync 的节点)

scp / rsync 传输实验结果                 sync push/pull (= rsync，但只传增量)

Jupyter notebook 在本地跑，数据在本地    peerpedia 在本地跑，repo 在本地
```

- 服务器不是一个神秘的"后端"——它就是集群上一个开着 `peerpedia serve` 的节点，和其他 peer 运行同一套代码
- 同步不是"提交表单到服务器"——就是 `rsync` 但只传 git diff，不传全量
- 离线不是"断网就白屏"——你的数据一直在 `~/.peerpedia/` 里，和 `.h5` 文件一样，网络只是用来同步

peerpedia 是**本地优先（local-first）**架构：所有操作默认在本地完成，sync 是后台行为。

### 安装包、服务器、本地的三角关系

```
                     peerpedia-core
                    (pip install 的唯一包)
                     /                  \
                    /                    \
        peerpedia article create     peerpedia serve
        peerpedia review submit      (接收 sync 请求)
        peerpedia sync push ────────────►  apply_bundle()
              (客户端)                    (服务器)
                    \                    /
                     \                  /
                  同一套 git_backend.py
                  同一套 models.py
                  同一套 crud_*.py
```

两端调用的核心函数完全一样，区别只在于**谁调用**和**数据目录里有多少内容**。

### 登录/权限代码：每个人硬盘上都有一份

`peerpedia serve` 作为子命令后，每个人的安装包里都有完整的 API 代码。但代码不会自己运行——只有在收到网络请求时才被触发：

```
你的笔记本（用户 A）                      课题组服务器（用户 B 在运行）
───────────────────                      ──────────────────────────

peerpedia article create ...             peerpedia serve
peerpedia review submit ...                │  等待请求
peerpedia sync push --server B             │
  │                                        │  收到 push 请求
  │  本地跑 assert_can_publish() ✓         │  ─────────────────
  │  "我是作者，允许"                       │  require_user()
  │                                        │    → 解析 JWT，确认身份
  │  不需要登录（你在自己机器上）            │
  │                                        │  assert_can_sync()
  └─────────────────────────────────────►  │    → "你是作者吗？"
                                           │    → 是 ✅，apply_bundle()
                                           │    → 不是 ❌，403
```

- **`policies/articles.py`** 在两端都跑，每次都跑——无论你是本地 `publish` 还是远程 `sync`
- **JWT / `require_user()`** 只在收到 HTTP 请求时才激活——不和网络交互时就是 dead code
- **`bcrypt` / 密码哈希** 在每台机器上都有——就像 `git` 二进制里包含 `git daemon` 代码一样

类比：`git` 的每个人安装都包含 `git daemon` 代码，但你不执行它时它就是磁盘上的字节。peerpedia 同理——`peerpedia serve` 没运行时，它只是一个你不用的子命令。

### 任何人都能搭建自己的 peerpedia 网络

peerpedia 不依赖"官方服务器"。同一个 `pip install peerpedia-core`，三种用法：

```
$ peerpedia article create ...    # 1. 单机离线
$ peerpedia serve                 # 2. 给实验室/课题组当服务器
$ peerpedia sync push \           # 3. 推到别人或自己的服务器
    --server https://physics-ucsb.example.com
```

和 git 一样：GitHub 很大，但 `git init --bare` 你自己随时搭。peerpedia 只是对学术评审流程做了同样的去中心化。

**但离真正的 P2P 还远。** 当前是星形拓扑（每个 client 只和一个 server 通信），不是对等 mesh。缺少的：节点发现（DHT/gossip）、对等冲突合并（当前只允许 fast-forward）、分布式身份（没有"哪张 users 表是对的"）。

### 同步协议：git bundle

每篇文章是一个独立的 git repo（`~/.peerpedia/articles/{id}/`）。同步传递的是 git objects 的增量包，不是数据库行：

```
本地 A                                  对等节点 B
───────                                 ──────────

1. GET  /api/v1/articles/{id}/head      ← B 的 HEAD hash

2. 如果 B 有新提交：
   GET  /api/v1/articles/{id}/bundle?since=<A_head>
   ← 增量 bundle，本地 apply_bundle()（仅 fast-forward）

3. 如果 A 有新提交：
   create_bundle(repo, B_head)            → 增量 bundle
   POST /api/v1/articles/{id}/sync        → B apply_bundle()
   如果 409（历史分叉）：先 pull 再重试

4. 首次推送（B 没有这篇文章）：
   tar.gz → base64 → POST /api/v1/articles → B 解包
```

### 关键设计决策

1. **Fast-forward only。** 拒绝分叉历史（返回 409）。必须先 pull、本地解决冲突、再 push。
2. **Git 是真相来源（SOT）。** 文章内容、评审、作者信息全在 git 里。数据库是缓存。
3. **作者邮箱编码用户 ID。** git commit 的 author email = `{uuid}@peerpedia`，可从 git history 反推作者身份。
4. **sedimentation 文章不可变。** `assert_can_sync_article` 只允许 `draft` 和 `published` 同步。
5. **离线队列。** `pending_ops.json`（`~/.peerpedia/pending_ops.json`）暂存离线操作。基础设施已存在但**未接入生产代码**。

### 代码层面的分工

| 模块 | 客户端 | 服务器 | 说明 |
|------|--------|--------|------|
| `git_backend.py` | 需要 | 需要 | `commit` / `get_commit_history` / `get_commit_authors` 两端都用 |
| `git_bundle.py` | 需要 | 需要 | `create_bundle` / `apply_bundle` / `find_common_ancestor` 两端都用 |
| `models.py` | 需要 | 需要 | 同一套 ORM |
| `policies/articles.py` | 需要 | 需要 | `assert_can_sync_article` 两端都用 |
| `bundle_client.py` | 需要 | 不需要 | 客户端 sync 编排 |
| `bundle_server.py` | 不需要 | 需要 | 服务端 handler（不含 HTTP） |
| `transport/http.py` | 需要 | 不需要 | 只有客户端发起 HTTP 请求 |
| `commands.py` | 需要 | 不需要 | 业务编排只在本地 |
| `cli.py` | 需要 | 不需要 | CLI 入口只在本地 |
| `workflow/scoring.py` | 需要 | 需要 | 评分计算两端都需（merge 后触发） |
| HTTP 路由 (`serve` 命令) | 不需要 | 需要 | 未来用 Starlette，调用 bundle_server |

### 阅读顺序

| 序号 | 文件 | 读什么 | 关键点 |
|------|------|--------|--------|
| 15 | [sync/network.py](../peerpedia_core/sync/network.py) | `is_online(server_url)` — GET `/health` | 5 秒超时 |
| 16 | [sync/bundle_client.py](../peerpedia_core/sync/bundle_client.py) | `sync(server, article_id)` → pull/push/merge 编排 | 完整递增 sync 协议，三种 case（server ahead / local ahead / diverged） |
| 17 | [sync/bundle_server.py](../peerpedia_core/sync/bundle_server.py) | `serve_get_head` / `serve_post_sync` / `serve_get_bundle` / `serve_get_ancestor` / `serve_post_articles` | 服务端 handler，不含 HTTP 代码 |
| 18 | [sync/transport/http.py](../peerpedia_core/sync/transport/http.py) | `fetch_head` / `push_bundle` / `fetch_bundle` / `ancestor_probe` / `post_article` | 唯一 import httpx 的文件 |
| 19 | [sync/pending_queue.py](../peerpedia_core/sync/pending_queue.py) | 文件队列 | 离线操作暂存 |
| 20 | [cli.py](../peerpedia_core/cli.py#L461-L482) | `_cmd_sync_status` / `_cmd_sync_push` | 遍历队列推送 |

**第四遍的目标：** 你能解释为什么服务器和客户端安装同一个 pip 包、区别只在数据目录和启动命令。


## 第五遍：理解入口（最后读）

入口代码是胶水层——理解它之前需要先理解下层。

| 序号 | 文件 | 读什么 |
|------|------|--------|
| 21 | [cli.py](../peerpedia_core/cli.py) | argparse 结构、`_resolve_user` 函数、`_parse_scores` 函数、Rich 输出 |
| 22 | [repl.py](../peerpedia_core/repl.py) | prompt_toolkit 交互式 REPL |
| 23 | [storage/compiler.py](../peerpedia_core/storage/compiler.py) | Markdown→HTML、Typst→PDF 编译后端、frontmatter 解析 |

---

## 第六遍：按改动模块定位（日常 Review 用）

日常 review PR 时不需重读所有文件。根据改动所在的模块，按以下索引定位：

### 改动在 `commands.py`

```
1. 先看 policies/articles.py —— 确认权限检查被正确调用
2. 看涉及的 crud_*.py —— 确认 DB 操作顺序
3. 看 git_backend.py —— 确认 Git 操作有对应的 DB 更新
4. 看 scoring.py / reputation.py —— 确认评分连锁更新
5. 看 cli.py —— 确认事务 commit 在 CLI 层
```

### 改动在 `crud_*.py`

```
1. 先看 models.py —— 确认字段约束没有被破坏
2. 看 commands.py —— 确认调用方没有被破坏
3. 看对应的 test_crud*.py —— 确认测试覆盖了新逻辑
```

### 改动在 `git_backend.py`

```
1. 先看 commands.py —— 确认所有 Git 调用点兼容
2. 看 tests/test_git_backend.py —— 确认测试覆盖
3. 看 sync/bundle_client.py 和 sync/bundle_server.py —— 它们直接调 git_backend
```

### 改动在 `sync/git_bundle.py`

```
1. 先看 sync/monotonic_search.py —— 确认搜索算法兼容
2. 看 sync/bundle_client.py 和 sync/bundle_server.py —— 确认 bundle 调用点兼容
3. 看 tests/test_sync.py —— 确认 bundle 测试覆盖
```

### 改动在 `policies/articles.py`

```
1. 先看 commands.py —— 确认每个 assert_can_* 的调用点
2. 看 cli.py —— 确认错误消息能正确展示给用户
3. 看 tests/test_policies.py —— 确认新增/修改的权限有测试
```

### 改动在 `workflow/*.py`（评分/沉淀/声誉）

```
1. 先看 params.py —— 确认参数用的是 params.xxx 而非硬编码
2. 看 scores.py —— 确认类型转换正确
3. 看 commands.py —— 确认 workflow 在正确时机被调用
4. 看对应的 test_workflow*.py —— 确认数值计算的边界条件
```

### 新增 CLI 命令

```
1. 先看 cli.py —— 确认命令注册、--json 支持、错误处理
2. 看 commands.py —— 确认业务逻辑在编排层
3. 看 policies/ —— 确认权限
4. 看 tests/test_commands.py —— 确认测试
```

---

## 快速跳转地图

按问题类型快速定位到正确的文件：

| 你想知道 | 去这里 |
|---------|--------|
| 文章有几种状态？每种状态能做什么？ | [policies/articles.py](../peerpedia_core/policies/articles.py) + [architecture.md](architecture.md) 状态机图 |
| 评分的 5 个维度是什么？怎么算的？ | [types/scores.py](../peerpedia_core/types/scores.py) + [workflow/scoring.py](../peerpedia_core/workflow/scoring.py) |
| 声誉怎么算？ | [workflow/reputation.py](../peerpedia_core/workflow/reputation.py) |
| 如何创建一个完整的文章？ | [commands.py](../peerpedia_core/commands.py) → `create_article_with_content()` |
| 事务在哪 commit？ | CLI 层——[cli.py](../peerpedia_core/cli.py) 每个命令的 `db.commit()` |
| Git repo 存在哪里？ | `~/.peerpedia/articles/<id>/` —— [git_backend.py:19](../peerpedia_core/storage/git_backend.py#L19) |
| DB 存在哪里？ | `~/.peerpedia/peerpedia.db` —— [cli.py:69-70](../peerpedia_core/cli.py#L69-L70) |
| 沉淀池自动发布逻辑？ | [workflow/sedimentation.py](../peerpedia_core/workflow/sedimentation.py) → `publish_ready_articles()` |
| 本地如何与服务器同步？ | [sync/bundle_client.py](../peerpedia_core/sync/bundle_client.py) → `push()` / `pull()` |
| sync 协议是什么？push 失败怎么办？ | [sync/bundle_client.py](../peerpedia_core/sync/bundle_client.py) — git bundle + k-exponential ancestor search + fast-forward + 409 重试 |
| 服务器 sync 端点在哪？ | [sync/bundle_server.py](../peerpedia_core/sync/bundle_server.py) — `serve_get_head` / `serve_post_sync` / `serve_get_bundle` / `serve_get_ancestor` / `serve_post_articles` |
| HTTP 传输实现在哪？ | [sync/transport/http.py](../peerpedia_core/sync/transport/http.py) — 唯一 import httpx 的文件，可插拔替换 |
| 离线时怎么暂存操作？ | [sync/pending_queue.py](../peerpedia_core/sync/pending_queue.py) — `~/.peerpedia/pending_ops.json` |
| 某个异常什么时候抛？ | [exceptions.py](../peerpedia_core/exceptions.py) + grep 调用点 |
| 测试怎么写的？ | [tests/conftest.py](../tests/conftest.py) → 临时 SQLite engine 的 fixture |

---

## 反模式：不要这样读

- ❌ **从 cli.py 开始读**——你会看到 argparse、Rich、subprocess 的噪音，错过架构约束
- ❌ **从 tests/ 开始读**——测试是验证层，不是解释层。先理解"应该做什么"再看"怎么验证"
- ❌ **跳过 architecture.md**——没有它你就只能在代码里反推分层规则
- ❌ **只读 diff 不读上下文**——改动的正确性取决于它所在的函数和模块的契约，diff 本身给不了这些信息
- ❌ **用 client-server 思维理解 sync**——服务器不是"后端"，是另一个跑同一套代码的节点。sync 是 rsync，不是 form POST
