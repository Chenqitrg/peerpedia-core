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
| 8 | [git_backend.py](../peerpedia_core/storage/git_backend.py) | `init_article_repo` / `commit_article` / `get_commit_history` / `get_diff` / `get_diff_between` / `create_bundle` / `apply_bundle` / `merge_git_repos` / `delete_article_repo` | Git 是第二个存储引擎 |
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

## 第四遍：理解入口（最后读）

入口代码是胶水层——理解它之前需要先理解下层。

| 序号 | 文件 | 读什么 |
|------|------|--------|
| 15 | [cli.py](../peerpedia_core/cli.py) | argparse 结构、`_resolve_user` 函数、`_parse_scores` 函数、Rich 输出 |
| 16 | [repl.py](../peerpedia_core/repl.py) | prompt_toolkit 交互式 REPL |
| 17 | [compiler.py](../peerpedia_core/storage/compiler.py) | Markdown→HTML、Typst→PDF 编译后端 |

---

## 第五遍：按改动模块定位（日常 Review 用）

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
3. 看 sync/bundle_sync.py —— bundle 操作依赖 Git backend
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
| 某个异常什么时候抛？ | [exceptions.py](../peerpedia_core/exceptions.py) + grep 调用点 |
| 测试怎么写的？ | [tests/conftest.py](../tests/conftest.py) → 临时 SQLite engine 的 fixture |

---

## 反模式：不要这样读

- ❌ **从 cli.py 开始读**——你会看到 argparse、Rich、subprocess 的噪音，错过架构约束
- ❌ **从 tests/ 开始读**——测试是验证层，不是解释层。先理解"应该做什么"再看"怎么验证"
- ❌ **跳过 architecture.md**——没有它你就只能在代码里反推分层规则
- ❌ **只读 diff 不读上下文**——改动的正确性取决于它所在的函数和模块的契约，diff 本身给不了这些信息
