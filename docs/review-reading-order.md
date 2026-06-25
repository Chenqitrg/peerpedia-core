# Review 文件阅读顺序

## 总原则

**Git 是内容真相源（SOT），DB 是元数据缓存。** 评审文件（scores.json、threads/*.md）先写入 git，再缓存到 DB。

## 建议阅读顺序

### Phase 0 — 前置概念

阅读代码前应理解以下关键设计决策：

1. **Git is SOT, DB is cache** — 所有用户内容（文章、评审、评论）先写入 git 工作树并提交，DB 只存结构化元数据（状态、评分缓存、关系）。完整性检查（`_verify_full` → `_repair_from_git`）可以从 git 重建 DB。
2. **Ed25519 密钥派生** — 密钥对从 password + scrypt salt 派生，与 git commit 签名使用相同的密钥。无存储密钥文件风险。
3. **TOFU（Trust On First Use）** — 第一次从 peer 同步时存储其公钥，后续同步验证提交签名是否匹配。密钥轮换需要主动通知协议。
4. **单主分支** — 文章 git 仓库只用 `main` 分支，无分支/标签。合并提案通过 git merge 实现，禁止 side branch。
5. **沉淀池（Sedimentation）** — 文章发布后进入 N 天沉淀期，期间接受评审，到期自动发布。评审者在沉淀期内匿名。
6. **评分 5 维度** — `origin`（原创性）、`rigor`（严谨性）、`reprod`（可复现性）、`mech`（机制理解）、`sig`（重要性）。每维 1-5 星。

### Phase 1 — 核心概念

1. [README.md](../README.md) — 项目概览 + 5 分钟上手
2. [architecture.md](architecture.md) — 完整文件树和分层规则
3. `peerpedia_core/exceptions.py` — 语义异常定义（BadRequestError、NotFoundError、PermissionError 等）
4. `peerpedia_core/types/scores.py` — 评分 5 维度的类型定义
5. `peerpedia_core/config/paths.py` — 数据目录布局（`~/.peerpedia/` 结构）
6. `peerpedia_core/config/params.py` — 全局参数（沉淀天数、评分阈值、速率限制）

### Phase 2 — 存储层

7. `peerpedia_core/storage/db/models.py` — ORM 模型表定义（User、Article、Review、Follow、Notification、MergeProposal 等）
8. `peerpedia_core/storage/db/engine.py` — SQLAlchemy 引擎 + 迁移 + JSONList/JSONDict 自定义类型
9. `peerpedia_core/storage/git_backend.py` — Git 操作（init、commit、diff、merge、checkout），与 DB 无关
10. `peerpedia_core/storage/db/crud_user.py` — User + Follow CRUD（注册、登录、关注/取消关注、密钥管理）
11. `peerpedia_core/storage/db/crud_article.py` — Article CRUD（创建、状态转换、fork_count 管理）
12. `peerpedia_core/storage/db/crud_review.py` — Review 评分缓存 CRUD，从 git 工作树同步，供评分聚合查询
13. `peerpedia_core/storage/db/crud_maintainer.py` — ScriptMaintainer CRUD，追踪谁管理文章（编辑/删除/发布/同步），与 git 作者正交
14. `peerpedia_core/storage/db/crud_merge.py` — MergeProposal CRUD（创建/接受/关闭合并提案）
15. `peerpedia_core/storage/db/crud_citation.py` — Citation CRUD（文章间引用关系，含前向/后向置信度）
16. `peerpedia_core/storage/db/crud_bookmark.py` — Bookmark CRUD（用户收藏文章）
17. `peerpedia_core/storage/db/crud_share.py` — Share CRUD（用户分享文章）
18. `peerpedia_core/storage/db/crud_notification.py` — Notification CRUD（通知创建/查询/标记已读）
19. `peerpedia_core/storage/db/crud_alias.py` — Alias CRUD（用户匿名身份映射，用于评审匿名化）

### Phase 3 — 业务逻辑

20. `peerpedia_core/policies/articles.py` — 权限检查（谁能编辑/删除/发布/评审文章）
21. `peerpedia_core/commands/` — 编排层，是唯一调用 storage/db/crud_* 的层
    - `articles.py` — 文章 CRUD 编排（create、edit、delete、publish、rollback、fork）
    - `reviews.py` — 评审流程（submit_review、submit_reply、评分写入 git + DB）
    - `merge.py` — 合并提案（propose_merge、accept_merge、withdraw_merge）
    - `maintainers.py` — 维护者管理（add、remove）
    - `bookmarks.py` — 书签管理
    - `shares.py` — 分享管理
    - `users.py` — 用户操作（注册、登录、删除、密钥更新）
    - `integrity.py` — 完整性修复（`_verify_full` → `_repair_from_git` → `_sync_status_from_git`）
    - `workflow.py` — 定时任务（`publish_ready_articles` 自动发布沉淀到期文章）
22. `peerpedia_core/commands/notifications.py` — 通知系统，thin facade over CRUD（查询、标记已读）
23. `peerpedia_core/commands/discover.py` — P2P 合并函数（merge_users、merge_follows、merge_followers、merge_article_meta），被 `social/exchange.py` 调用
24. `peerpedia_core/commands/views.py` — API 序列化层，返回 `dict`/`list[dict]`，transport 和 CLI 共用
25. `peerpedia_core/commands/trailers.py` — Git commit trailer 解析（`Closes:` / `Acked-by:`），用于评审工作流和声誉计算
26. `peerpedia_core/commands/bundle.py` — 同步编排（`sync_reviews_from_worktree`、`apply_sync_bundle`），桥接 git 内容与 DB 缓存
27. `peerpedia_core/workflow/scoring.py` — 评分聚合算法（`recompute_article_score`），从 Review 缓存计算加权评分
28. `peerpedia_core/workflow/reputation.py` — 声誉计算（`compute_author_reputation`），基于评审活动、被引、评审权重
29. `peerpedia_core/workflow/sedimentation.py` — 沉淀池纯函数（`is_ready_to_publish`、`apply_no_review_penalty`），零 IO
30. `peerpedia_core/workflow/state.py` — 不可变算法输入（`ReputationState`），是 orchestrator 与纯算法之间的契约接口

### Phase 4 — 网络层

31. `peerpedia_core/transport/http_server.py` — Starlette ASGI 服务器（路由注册、AuthMiddleware、异常处理）
32. `peerpedia_core/transport/http_client.py` — httpx HTTP 客户端（fetch_head、push_bundle、fetch_following 等）
33. `peerpedia_core/transport/auth.py` — Ed25519 签名认证（Authorization header 生成与验证，±30s 防重放）
34. `peerpedia_core/transport/routes/` — HTTP 路由处理器，解析请求后委托给 `commands/`：
    - `articles.py` — 文章路由（GET head/bundle/sync、POST sync）
    - `users.py` — 用户路由（following/followers/articles/follow/unfollow）
    - `peers.py` — Peer 发现路由（GET /api/v1/peers 返回已知 peer URL）
35. `peerpedia_core/bundle/client.py` — P2P 同步客户端（sync_article 协议：fetch_head → ancestor_probe → fetch_incremental_bundle / push_bundle）
36. `peerpedia_core/bundle/server.py` — 服务端 bundle 处理器（get_head、get_bundle、apply_sync），与 HTTP 层分离
37. `peerpedia_core/bundle/git_bundle.py` — 纯 git bundle 协议（create_bundle、ingest_bundle、find_common_ancestor），最底层同步协议
38. `peerpedia_core/bundle/pending.py` — 离线操作队列（JSON 文件存储，网络恢复时重放 push/delete）
39. `peerpedia_core/bundle/monotonic.py` — k-exponential 单调搜索算法，用于查找共同祖先
40. `peerpedia_core/social/exchange.py` — 社交图交换编排（fetch-then-merge：fetch_following → merge_follows）
41. `peerpedia_core/social/discovery.py` — P2P peer 发现（从已知 peer 发现新 peer）

### Phase 5 — CLI

42. `peerpedia_core/cli/parser.py` — 命令表 + argparse 定义（全部命令及其参数）
43. `peerpedia_core/cli/helpers.py` — 共享工具（session 管理、编辑器调用、`_with_db` 装饰器、DB 初始化）
44. `peerpedia_core/cli/display.py` — Rich 输出帮助（console、Panel、Table、Theme），layer 0，只依赖 rich
45. `peerpedia_core/cli/bundle_utils.py` — 自动同步帮助（push/pull 所有本地文章），layer 1，依赖 helpers + bundle/
46. `peerpedia_core/cli/handlers/` — 命令实现（articles.py、reviews.py、social.py、merge.py、admin.py 等）

### Historical Docs

- [user-flow-audit.md](user-flow-audit.md) — 2026-06-24 用户流审计，**2026-06-25 更新：10 项已修复**。覆盖 20 阶段，原 35 个缺口，7 个 MVP 阻塞项中 4 个已解决
- [layer-audit.md](layer-audit.md) — 分层审计，**状态：标记为 NEVER IMPLEMENTED（2026-06-25）**。描述了一次从未执行的 `sync/ → server/` 重构计划，当前实际使用 `bundle/` + `transport/` 架构。架构约束已通过 `test_architecture.py` 强制执行
- [design-review-report.md](design-review-report.md) — 2026-06-24 CLI 设计审查，**标记为 HISTORICAL（2026-06-24）**。多数问题已修复（tab 补全、help handler、_ok 消息）。综合评分 4/10
- [cli-refactor-notes.md](cli-refactor-notes.md) — 2026-06-24 CLI 重构记录
- [git-db-consistency-gaps.md](git-db-consistency-gaps.md) — 2026-06-24 Git/DB 一致性分析，**全部 gap 已修复（2026-06-25）**。G1、G2b、G3、G9 均已通过 `_reset_sink()` 原子写入和 `sync_reviews_from_worktree` 修复
- [test-coverage-report.md](test-coverage-report.md) — 当前覆盖率报告
