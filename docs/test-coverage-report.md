# 单元测试覆盖率报告

**日期:** 2026-06-24
**分支:** main
**测试工具:** pytest 9.1.0 + pytest-cov 7.1.0 + coverage 7.14.2
**Python:** 3.14.5

---

## 总览

| 指标 | 数值 |
|------|------|
| **总行覆盖率** | **63.1%** (2394/3791 statements) |
| **测试文件数** | 31 |
| **测试用例数** | 451（448 通过，3 失败） |
| **源文件数** | 88 |
| **100% 覆盖文件** | 22 (25%) |
| **低于 50% 覆盖文件** | 21 (24%) |
| **无专属测试的文件** | 32 |

---

## 按子包覆盖率

```
config       ██████████ 100.0%  (60 stmts)
types        ██████████ 100.0%  (38 stmts)
workflow     ██████████  98.7%  (76 stmts)
social       █████████░  96.2%  (26 stmts)
policies     █████████░  93.1%  (72 stmts)
storage      ████████░░  87.9% (708 stmts)
commands     ███████░░░  79.3% (847 stmts)
bundle       ██████░░░░  68.0% (294 stmts)
(top-level)  █████░░░░░  57.5% (315 stmts)
transport    ████░░░░░░  46.1% (542 stmts)
cli          ██░░░░░░░░  25.1% (813 stmts)
─────────────────────────────────
OVERALL      ██████░░░░  63.1% (3791 stmts)
```

| 子包 | 文件数 | 覆盖率 | 状态 |
|------|--------|--------|------|
| `config/` | 4 | 100.0% | 🟢 优秀 |
| `types/` | 2 | 100.0% | 🟢 优秀 |
| `workflow/` | 4 | 98.7% | 🟢 优秀 |
| `social/` | 2 | 96.2% | 🟢 优秀 |
| `policies/` | 2 | 93.1% | 🟢 良好 |
| `storage/` | 14 | 87.9% | 🟢 良好 |
| `commands/` | 19 | 79.3% | ⚠️ 一般 |
| `bundle/` | 6 | 68.0% | ⚠️ 偏低 |
| `(top-level)` | 6 | 57.5% | ⚠️ 偏低 |
| `transport/` | 14 | 46.1% | 🔴 严重 |
| `cli/` | 15 | 25.1% | 🔴 严重 |

---

## 各子包详细

### 🟢 config/ — 100.0%（60 stmts, 0 missed）

| File | Stmts | Miss | Cover% |
|------|-------|------|--------|
| 🟢 `config/git.py` | 14 | 0 | 100.0% |
| 🟢 `config/params.py` | 36 | 0 | 100.0% |
| 🟢 `config/paths.py` | 10 | 0 | 100.0% |

**测试文件:** `test_params.py`（直接覆盖 `params.py`），其余通过集成测试覆盖。

### 🟢 types/ — 100.0%（38 stmts, 0 missed）

| File | Stmts | Miss | Cover% |
|------|-------|------|--------|
| 🟢 `types/scores.py` | 38 | 0 | 100.0% |

**测试文件:** `test_types.py` — 覆盖 `FiveDimScores`（5 维评分）和 `ReputationScores`（4 维声望）的构造、夹紧、融合逻辑。

### 🟢 workflow/ — 98.7%（76 stmts, 1 missed）

| File | Stmts | Miss | Cover% |
|------|-------|------|--------|
| 🟢 `workflow/sedimentation.py` | 14 | 1 | 92.9% |
| 🟢 `workflow/reputation.py` | 30 | 0 | 100.0% |
| 🟢 `workflow/scoring.py` | 32 | 0 | 100.0% |

**测试文件:** `test_reputation.py`, `test_workflow.py`, `test_sedimentation_publish.py`。
**Missing:** `sedimentation.py:33` — `apply_no_review_penalty` 的边缘情况。

### 🟢 social/ — 96.2%（26 stmts, 1 missed）

| File | Stmts | Miss | Cover% |
|------|-------|------|--------|
| 🟢 `social/exchange.py` | 24 | 1 | 95.8% |

**测试文件:** `test_social_exchange.py` — 覆盖 `discover_following`, `discover_followers`, `discover_articles`。

### 🟢 policies/ — 93.1%（72 stmts, 5 missed）

| File | Stmts | Miss | Cover% |
|------|-------|------|--------|
| 🟢 `policies/articles.py` | 72 | 5 | 93.1% |

**测试文件:** `test_policies.py` — 覆盖所有 `assert_can_*` 权限检查函数。5 行 miss 在边缘权限组合。

### 🟢 storage/ — 87.9%（708 stmts, 86 missed）

| File | Stmts | Miss | Cover% |
|------|-------|------|--------|
| ⚠️ `storage/git_backend.py` | 177 | 50 | 71.8% |
| ⚠️ `storage/db/crud_user.py` | 79 | 18 | 77.2% |
| 🟢 `storage/db/crud_article.py` | 120 | 10 | 91.7% |
| 🟢 `storage/db/crud_review.py` | 21 | 1 | 95.2% |
| 🟢 `storage/db/crud_merge.py` | 28 | 1 | 96.4% |
| 🟢 `storage/db/engine.py` | 59 | 2 | 96.6% |
| 🟢 `storage/locks.py` | 42 | 1 | 97.6% |
| 🟢 `storage/db/models.py` | 98 | 2 | 98.0% |
| 🟢 `storage/db/crud_bookmark.py` | 16 | 0 | 100.0% |
| 🟢 `storage/db/crud_citation.py` | 21 | 0 | 100.0% |
| 🟢 `storage/db/crud_maintainer.py` | 17 | 0 | 100.0% |
| 🟢 `storage/db/session_utils.py` | 20 | 0 | 100.0% |

**测试文件:** `test_git_backend.py`, `test_get_commit_authors.py`, `test_locks.py`, `test_models.py`, `test_session_utils.py`, `test_crud.py`, `test_crud_article.py`。

**主要缺口:**
- `git_backend.py`（71.8%）: merge conflict 逻辑、签名验证、错误处理路径未覆盖
- `crud_user.py`（77.2%）: `generate_anonymous_name`/`derive_anonymous_name` 函数未测试

### ⚠️ commands/ — 79.3%（847 stmts, 175 missed）

| File | Stmts | Miss | Cover% |
|------|-------|------|--------|
| 🔴 `commands/articles/delete.py` | 19 | 10 | 47.4% |
| ⚠️ `commands/views.py` | 33 | 16 | 51.5% |
| ⚠️ `commands/reviews.py` | 68 | 31 | 54.4% |
| ⚠️ `commands/users.py` | 25 | 11 | 56.0% |
| ⚠️ `commands/bookmarks.py` | 9 | 3 | 66.7% |
| ⚠️ `commands/discover.py` | 77 | 22 | 71.4% |
| ⚠️ `commands/articles/__init__.py` | 36 | 10 | 72.2% |
| ⚠️ `commands/integrity.py` | 84 | 23 | 72.6% |
| 🟢 `commands/bundle.py` | 87 | 16 | 81.6% |
| 🟢 `commands/articles/publish.py` | 46 | 7 | 84.8% |
| 🟢 `commands/articles/update.py` | 55 | 7 | 87.3% |
| 🟢 `commands/maintainers.py` | 34 | 4 | 88.2% |
| 🟢 `commands/__init__.py` | 30 | 3 | 90.0% |
| 🟢 `commands/articles/rollback.py` | 40 | 4 | 90.0% |
| 🟢 `commands/articles/create.py` | 33 | 2 | 93.9% |
| 🟢 `commands/articles/_helpers.py` | 17 | 1 | 94.1% |
| 🟢 `commands/articles/fork.py` | 27 | 1 | 96.3% |
| 🟢 `commands/workflow.py` | 81 | 3 | 96.3% |
| 🟢 `commands/merge.py` | 46 | 1 | 97.8% |

**测试文件:** `test_commands.py`, `test_bundle_commands.py`, `test_maintainers.py`, `test_merge.py`, `test_workflow.py`, `test_sedimentation_publish.py`, `test_social_exchange.py`。

**主要缺口:**
- `reviews.py`（54.4%）: 评审提交流程大部分未测试，包括匿名 ID 派生和 Git 写入
- `views.py`（51.5%）: 无专属测试文件，所有 view 聚合查询未测试
- `users.py`（56.0%）: search_users 和 follow/unfollow 包装函数未测试
- `bookmarks.py`（66.7%）: 无专属测试文件
- `delete.py`（47.4%）: 文章删除的错误路径未覆盖
- `integrity.py`（72.6%）: 签名验证路径未测试

### ⚠️ bundle/ — 68.0%（294 stmts, 94 missed）

| File | Stmts | Miss | Cover% |
|------|-------|------|--------|
| 🔴 `bundle/client.py` | 71 | 51 | 28.2% |
| ⚠️ `bundle/server.py` | 39 | 11 | 71.8% |
| ⚠️ `bundle/git_bundle.py` | 98 | 25 | 74.5% |
| 🟢 `bundle/pending.py` | 39 | 6 | 84.6% |
| 🟢 `bundle/monotonic.py` | 43 | 1 | 97.7% |

**测试文件:** `test_bundle.py`, `test_monotonic_search.py`, `test_bundle_commands.py`。
**主要缺口:** `client.py`（28.2%）— 整个 HTTP sync flow（`sync_article`, `pull_incremental`, `push_incremental`）未在单元层测试，依赖集成测试。

### ⚠️ (top-level) — 57.5%（315 stmts, 134 missed）

| File | Stmts | Miss | Cover% |
|------|-------|------|--------|
| 🔴 `repl.py` | 145 | 111 | 23.4% |
| ⚠️ `crypto.py` | 64 | 16 | 75.0% |
| 🟢 `frontmatter.py` | 33 | 5 | 84.8% |
| 🟢 `compiler.py` | 63 | 2 | 96.8% |
| 🟢 `exceptions.py` | 10 | 0 | 100.0% |

**测试文件:** `test_compiler.py`, `test_exceptions.py`。其余通过集成测试覆盖。
**主要缺口:** `repl.py`（23.4%）— 交互式 REPL 完全无测试；`crypto.py`（75.0%）— Ed25519 签名/验证/密钥派生部分未测试。

### 🔴 transport/ — 46.1%（542 stmts, 292 missed）

| File | Stmts | Miss | Cover% |
|------|-------|------|--------|
| 🔴 `transport/auth.py` | 48 | 40 | 16.7% |
| 🔴 `transport/http_client.py` | 187 | 146 | 21.9% |
| 🔴 `transport/routes/articles.py` | 91 | 55 | 39.6% |
| ⚠️ `transport/middleware/auth.py` | 40 | 20 | 50.0% |
| ⚠️ `transport/health.py` | 18 | 8 | 55.6% |
| ⚠️ `transport/routes/users.py` | 39 | 16 | 59.0% |
| 🟢 `transport/middleware/db.py` | 21 | 2 | 90.5% |
| 🟢 `transport/http_server.py` | 49 | 4 | 91.8% |
| 🟢 `transport/middleware/ratelimit.py` | 22 | 1 | 95.5% |
| 🟢 `transport/middleware/logging.py` | 13 | 0 | 100.0% |
| 🟢 `transport/shared.py` | 6 | 0 | 100.0% |

**测试文件:** `test_http_transport.py`, `test_auth_middleware.py`, `test_server.py`。
**主要缺口:**
- `http_client.py`（21.9%）: 15 个 HTTP fetch/push 函数均未测试（需 mock `httpx`）
- `auth.py`（16.7%）: `sign_auth_header`/`verify_auth_header` 协议几乎未测试
- `routes/articles.py`（39.6%）: 10 个 async handler 只有 2 个被 server 集成测试间接覆盖
- `routes/users.py`（59.0%）: 5 个 handler 部分通过 server 测试覆盖

### 🔴 cli/ — 25.1%（813 stmts, 609 missed）

| File | Stmts | Miss | Cover% |
|------|-------|------|--------|
| 🔴 `cli/handlers/articles.py` | 153 | 133 | 13.1% |
| 🔴 `cli/handlers/reviews.py` | 50 | 41 | 18.0% |
| 🔴 `cli/handlers/account.py` | 85 | 68 | 20.0% |
| 🔴 `cli/handlers/social.py` | 130 | 101 | 22.3% |
| 🔴 `cli/bundle_utils.py` | 53 | 41 | 22.6% |
| 🔴 `cli/handlers/bundle.py` | 55 | 40 | 27.3% |
| 🔴 `cli/helpers.py` | 112 | 81 | 27.7% |
| 🔴 `cli/handlers/compile_.py` | 16 | 11 | 31.2% |
| 🔴 `cli/handlers/maintainers.py` | 31 | 21 | 32.3% |
| 🔴 `cli/__init__.py` | 24 | 16 | 33.3% |
| 🔴 `cli/display.py` | 40 | 26 | 35.0% |
| 🔴 `cli/handlers/server.py` | 5 | 3 | 40.0% |
| 🔴 `cli/parser.py` | 45 | 26 | 42.2% |
| 🟢 `cli/handlers/mother.py` | 5 | 1 | 80.0% |

**测试文件:** 无专属 CLI 测试文件。CLI 代码仅通过 `test_commands.py` 和集成测试间接覆盖。
**核心问题:** 15 个 CLI 文件共用 0 个专属测试文件。handler 函数被 `parser.py` 调用，但 argument parsing、error formatting、display 输出均无自动化验证。

---

## Top 20 覆盖率缺口

按 `missed_statements × (1 - coverage%)` 排序，同时考虑绝对缺失和相对严重程度：

| # | File | Stmts | Miss | Cover% | Severity |
|---|------|-------|------|--------|----------|
| 1 | `cli/handlers/articles.py` | 153 | 133 | 13.1% | 116 |
| 2 | `transport/http_client.py` | 187 | 146 | 21.9% | 114 |
| 3 | `repl.py` | 145 | 111 | 23.4% | 85 |
| 4 | `cli/handlers/social.py` | 130 | 101 | 22.3% | 78 |
| 5 | `cli/helpers.py` | 112 | 81 | 27.7% | 59 |
| 6 | `cli/handlers/account.py` | 85 | 68 | 20.0% | 54 |
| 7 | `bundle/client.py` | 71 | 51 | 28.2% | 37 |
| 8 | `cli/handlers/reviews.py` | 50 | 41 | 18.0% | 34 |
| 9 | `transport/auth.py` | 48 | 40 | 16.7% | 33 |
| 10 | `transport/routes/articles.py` | 91 | 55 | 39.6% | 33 |
| 11 | `cli/bundle_utils.py` | 53 | 41 | 22.6% | 32 |
| 12 | `cli/handlers/bundle.py` | 55 | 40 | 27.3% | 29 |
| 13 | `cli/display.py` | 40 | 26 | 35.0% | 17 |
| 14 | `cli/parser.py` | 45 | 26 | 42.2% | 15 |
| 15 | `cli/handlers/maintainers.py` | 31 | 21 | 32.3% | 14 |
| 16 | `commands/reviews.py` | 68 | 31 | 54.4% | 14 |
| 17 | `storage/git_backend.py` | 177 | 50 | 71.8% | 14 |
| 18 | `cli/__init__.py` | 24 | 16 | 33.3% | 11 |
| 19 | `transport/middleware/auth.py` | 40 | 20 | 50.0% | 10 |
| 20 | `commands/views.py` | 33 | 16 | 51.5% | 8 |

---

## 测试健康状态

### 失败的测试（3 个）

| 测试 | 错误类型 | 原因分析 |
|------|----------|----------|
| `test_bundle_commands.py::TestApplySyncBundle::test_ff_only_merge_success` | `ValueError: Repo has no commits` | 测试创建的 repo 缺少初始 commit，`get_head_hash` 断言失败 |
| `test_merge.py::TestAcceptMerge::test_success` | `git.exc.NoSuchPathError` | `~/.peerpedia/articles/art-target-pub` 不存在，测试依赖本地状态 |
| `test_merge.py::TestAcceptMerge::test_published_target_triggers_sedimentation` | `git.exc.NoSuchPathError` | 同上，测试隔离问题 |

**根因:** 2 个测试依赖 `~/.peerpedia/articles/` 下的预存 repo，而非创建 temp 目录。当这些 repo 被清理或不存在时测试失败。

### 资源泄漏警告（15 个）

15 个 `ResourceWarning: unclosed database` 警告分布在多个测试文件中。表明 SQLAlchemy session 未正确关闭。影响：CI 日志噪音，极端情况下可能耗尽文件描述符。

### Starlette 弃用警告

`test_server.py` 使用 `from starlette.testclient import TestClient`，Starlette 已弃用 httpx 后端，建议迁移到 `httpx2`。

---

## 架构规则测试

`test_architecture.py`（685 行）强制检查 CLAUDE.md 中的导入分层规则：
- ✅ `transport/` 只能导入 `httpx`/`starlette`
- ✅ `storage/git_backend.py` + `bundle/git_bundle.py` 只能导入 `git`
- ✅ `storage/db/` 只能导入 `sqlalchemy`
- ✅ `commands/` + `storage/db/` 只能从 `storage/db/crud_*.py` 导入
- ✅ Foundation 模块禁止导入 `bundle/`, `social/`, `transport/`

**448 个架构测试通过，无违反。**

---

## 建议行动

按优先级排序：

### P0 — 修复失败测试
- 修复 3 个失败的测试：将 `~/.peerpedia/articles/` 依赖改为 `tmp_path` fixture
- 预估：30 min

### P1 — CLI handler 测试（当前 25.1% → 目标 60%+）
- 为每个 `cli/handlers/*.py` 添加测试，mock `commands/` 层
- 先覆盖 `articles.py`（133 missed）和 `social.py`（101 missed）
- 预估：4-6h

### P2 — Transport 层测试（当前 46.1% → 目标 70%+）
- 用 `pytest-httpx` mock HTTP 调用，测试 `http_client.py` 所有 fetch/push 函数
- 测试 `transport/auth.py` 的 sign/verify 协议
- 测试 `transport/routes/articles.py` 的所有 route handler
- 预估：3-4h

### P3 — REPL 测试（当前 23.4% → 目标 70%+）
- 测试 `repl.py` 的 `_dispatch` 函数，mock stdin/stdout
- 覆盖 help、user、article 命令分发
- 预估：1-2h

### P4 — 补全 commands/ 测试（当前 79.3% → 目标 90%+）
- 为 `commands/reviews.py` 添加评审提交测试
- 为 `commands/views.py` 添加视图查询测试
- 为 `commands/bookmarks.py` 添加书签测试
- 预估：2-3h

### P5 — 清理
- 修复 15 个 `ResourceWarning`（session 未关闭）
- Starlette TestClient → httpx2 迁移
- 预估：1h
