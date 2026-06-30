# Review 文件阅读顺序

## 总原则

**Git 是内容真相源（SOT），DB 是元数据缓存。** 评审文件（scores.json、threads/*.md）先写入 git，再缓存到 DB。

## 建议阅读顺序

### Phase 0 — 前置概念

阅读代码前应理解以下关键设计决策：

1. **Git is SOT, DB is cache** — 所有用户内容（文章、评审、评论）先写入 git 工作树并提交，DB 只存结构化元数据（状态、评分缓存、关系）。完整性检查可以从 git 重建 DB。
2. **Ed25519 密钥派生** — 密钥对从 password + scrypt salt 派生，与 git commit 签名使用相同的密钥。无存储密钥文件风险。
3. **TOFU（Trust On First Use）** — 第一次从 peer 同步时存储其公钥，后续同步验证提交签名是否匹配。密钥轮换需要主动通知协议。
4. **单主分支** — 文章 git 仓库只用 `main` 分支，无分支/标签。合并提案通过 git merge 实现，禁止 side branch。
5. **沉淀池（Sedimentation）** — 文章发布后进入 N 天沉淀期，期间接受评审，到期自动发布。
6. **评分 5 维度** — `originality`（原创性）、`rigor`（严谨性）、`completeness`（完整性）、`pedagogy`（教学性）、`impact`（影响力）。每维 1-5 星。

### Phase 1 — 核心概念

1. [README.md](../README.md) — 项目概览 + 5 分钟上手
2. [architecture.md](architecture.md) — 完整文件树和分层规则（架构测试强制执行）
3. `peerpedia_core/__main__.py` — 顶层路由器（cli/ 和 repl/ 的唯一交汇点）
4. `peerpedia_core/exceptions.py` — 语义异常定义（PeerpediaError, NotFoundError, BadRequestError, ConflictError 等）
5. `peerpedia_core/messages.py` — 176 条结构化消息注册表（code → text + kind + suggestion + see_also）
6. `peerpedia_core/types/scores.py` — 评分 5 维度的类型定义 + SCORE_DIMENSIONS
7. `peerpedia_core/types/status.py` — 文章状态常量
8. `peerpedia_core/config/paths.py` — 数据目录布局（`~/.peerpedia/` 结构）
9. `peerpedia_core/config/params.py` — 全局参数（沉淀天数、评分阈值、速率限制）

### Phase 2 — 存储层

10. `peerpedia_core/storage/db/models.py` — ORM 模型（User, Article, Review, Follow, Notification, MergeProposal 等）
11. `peerpedia_core/storage/db/engine.py` — SQLAlchemy 引擎 + 迁移 + JSONList/JSONDict 自定义类型
12. `peerpedia_core/storage/git/ops.py` — Git 核心操作（init、commit、status、diff）
13. `peerpedia_core/storage/git/read.py` — Git 读取（source, head, history, authors）
14. `peerpedia_core/storage/git/bundle.py` — Git bundle 创建/应用
15. `peerpedia_core/storage/git/archive.py` — tar.gz 打包/解包（首次上传）
16. `peerpedia_core/storage/git/guards.py` — Git 层 guard（require_article_repo）
17. `peerpedia_core/storage/db/crud_article.py` — Article CRUD（创建、状态转换、fork_count 管理）
18. `peerpedia_core/storage/db/crud_user.py` — User + Follow CRUD（注册、登录、关注/取消关注、密钥管理）
19. `peerpedia_core/storage/db/crud_review.py` — Review 评分缓存 CRUD
20. `peerpedia_core/storage/db/crud_maintainer.py` — Maintainer CRUD（协作者管理）
21. `peerpedia_core/storage/db/crud_merge.py` — MergeProposal CRUD
22. `peerpedia_core/storage/db/crud_notification.py` — Notification CRUD
23. `peerpedia_core/storage/db/crud_alias.py` — Alias CRUD（用户别名）
24. `peerpedia_core/storage/db/crud_bookmark.py` — Bookmark CRUD
25. `peerpedia_core/storage/db/crud_share.py` — Share CRUD
26. `peerpedia_core/storage/db/crud_citation.py` — Citation CRUD

### Phase 3 — 业务逻辑（core/）

27. `peerpedia_core/rules/articles.py` — 权限检查（谁能编辑/删除/发布/评审文章）
28. `peerpedia_core/rules/reviews.py` — 评审权限检查
29. `peerpedia_core/core/__init__.py` — Facade：导出所有公共函数
30. `peerpedia_core/core/articles/create.py` — `create_article_with_content`
31. `peerpedia_core/core/articles/update.py` — `update_article_content`
32. `peerpedia_core/core/articles/publish.py` — `publish_article`
33. `peerpedia_core/core/articles/fork.py` — `fork_article`
34. `peerpedia_core/core/articles/rollback.py` — `rollback_article`
35. `peerpedia_core/core/articles/delete.py` — `delete_article`
36. `peerpedia_core/core/articles/diff.py` — `diff_article`
37. `peerpedia_core/core/articles/sink.py` — `publish_ready_articles`（沉淀池定时器）
38. `peerpedia_core/core/articles/_helpers.py` — 共享辅助（require_article, rebuild_article_authors, _reset_sink）
39. `peerpedia_core/core/reviews/submit.py` — `submit_review`（git-first: write → commit → DB cache）
40. `peerpedia_core/core/reviews/invite.py` — 评审邀请（invite/accept/decline）
41. `peerpedia_core/core/reviews/thread.py` — `submit_reply`（评审回复/讨论串）
42. `peerpedia_core/core/users.py` — 用户操作（注册、登录、删除、密钥更新、关注/取消关注）
43. `peerpedia_core/core/views.py` — API 序列化层（get_article_view, get_user_view, get_following_views）
44. `peerpedia_core/core/merge.py` — 合并提案（propose/accept/withdraw）
45. `peerpedia_core/core/maintainers.py` — 维护者管理（add/remove/consent/revoke）
46. `peerpedia_core/core/bookmarks.py` — 书签管理
47. `peerpedia_core/core/shares.py` — 分享管理
48. `peerpedia_core/core/notifications.py` — 通知系统 facade
49. `peerpedia_core/core/guards.py` — 共享 guard helpers
50. `peerpedia_core/core/sync_article.py` — 文章同步编排（k-exponential probe 协议）
51. `peerpedia_core/core/sync_social.py` — 社交图同步（discover_following, discover_followers）
52. `peerpedia_core/core/reconcile/mirror.py` — Git→DB 镜像（从 git 读取权威状态，写回 DB 缓存）
53. `peerpedia_core/core/reconcile/score.py` — 评分协调

### Phase 4 — 纯计算层（compute/）

54. `peerpedia_core/compute/scoring.py` — 评分聚合（aggregate_review_scores，加权平均）
55. `peerpedia_core/compute/sedimentation.py` — 沉淀池纯函数（is_ready_to_publish, apply_no_review_penalty）
56. `peerpedia_core/compute/reputation.py` — 声誉计算（compute_reputation, blend_reputation）
57. `peerpedia_core/compute/monotonic.py` — k-exponential 单调搜索（ancestor probe 算法）
58. `peerpedia_core/compute/bfs.py` — 图遍历（社交图发现）
59. `peerpedia_core/compute/state.py` — 不可变算法输入（ReputationState, snapshots）

### Phase 5 — 网络层

60. `peerpedia_core/transport/__init__.py` — Transport dataclass（bundle of fetch_*/push_* callbacks）
61. `peerpedia_core/transport/auth.py` — Ed25519 签名认证（Authorization header 生成与验证，±30s 防重放）
62. `peerpedia_core/transport/http/_core.py` — 共享 HTTP 基础设施（client pool, signed get/post）
63. `peerpedia_core/transport/http/articles.py` — 文章 HTTP 调用（head, bundle, repo, source, search）
64. `peerpedia_core/transport/http/social.py` — 社交 HTTP 调用（follow, share, peers, school）
65. `peerpedia_core/transport/http/health.py` — 健康检查 + 时钟偏差
66. `peerpedia_core/server/app.py` — Starlette ASGI app 工厂（create_app）
67. `peerpedia_core/server/middleware/auth.py` — Auth 中间件（PEERPEDIA_SKIP_AUTH 可绕过）
68. `peerpedia_core/server/middleware/db.py` — DB session 中间件
69. `peerpedia_core/server/middleware/ratelimit.py` — 速率限制
70. `peerpedia_core/server/routes/articles.py` — 文章路由（GET head/bundle/sync、POST sync）
71. `peerpedia_core/server/routes/users.py` — 用户路由（following/followers/articles/follow/unfollow）
72. `peerpedia_core/server/routes/peers.py` — Peer 发现路由

### Phase 6 — App 层（facade）

73. `peerpedia_core/app/context.py` — AppContext（db + transport + session）
74. `peerpedia_core/app/result.py` — AppResult / AppNotice 类型
75. `peerpedia_core/app/refs.py` — require_article, require_user, require_user_by_ref
76. `peerpedia_core/app/parsers.py` — 输入解析（scores, refs）
77. `peerpedia_core/app/commands/article.py` — 文章命令 facade（create, show, list, edit, publish...）
78. `peerpedia_core/app/commands/account.py` — 账户命令 facade（register, login, whoami, search...）
79. `peerpedia_core/app/commands/social.py` — 社交命令 facade（follow, school, bookmark, share...）
80. `peerpedia_core/app/commands/review.py` — 评审命令 facade（submit, list, reply, invite...）
81. `peerpedia_core/app/commands/sync.py` — 同步命令 facade
82. `peerpedia_core/app/commands/dashboard.py` — 仪表盘（count_user_articles, publish_ready）
83. `peerpedia_core/app/commands/display.py` — CLI 数据查找（resolve_author_names, list_articles）

### Phase 7 — CLI + REPL

84. `peerpedia_core/cli/__init__.py` — CLI 入口（main：parse args, dispatch）
85. `peerpedia_core/cli/parser.py` — 命令表 + argparse 构建（全部命令及其参数）
86. `peerpedia_core/cli/decorators.py` — @with_context 装饰器（DB session + render + auto-sync）
87. `peerpedia_core/cli/display.py` — Rich 输出（display_article, display_user, display_diff, _print_table, _stars）
88. `peerpedia_core/cli/info.py` — 核心输出引擎（_out, _render_result, _render_error, _render_data）
89. `peerpedia_core/cli/session.py` — Session 读写
90. `peerpedia_core/cli/dispatch.py` — 命令派发表
91. `peerpedia_core/cli/bundle_utils.py` — 自动同步帮助（_try_sync, _resolve_server_url）
92. `peerpedia_core/cli/cmds/article.py` — 文章命令 handler（create, show, list, edit, publish...）
93. `peerpedia_core/cli/cmds/account.py` — 账户命令 handler（register, login, whoami, search...）
94. `peerpedia_core/cli/cmds/social.py` — 社交命令 handler（follow, school, bookmark, share...）
95. `peerpedia_core/cli/cmds/reviews.py` — 评审命令 handler（submit, list, reply, invite...）
96. `peerpedia_core/cli/cmds/mother.py` — 交互式用户指南
97. `peerpedia_core/repl/__init__.py` — REPL 入口（run：启动 banner、定时扫描、命令循环）
98. `peerpedia_core/repl/dispatch.py` — REPL 元命令 + CLI 桥接
99. `peerpedia_core/repl/browse.py` — 全屏交互视图（文章浏览器、用户排行榜、评审查看器）
100. `peerpedia_core/repl/state.py` — REPL 状态（主题定义、会话变量、prompt 构建、自动补全）

### Historical Docs

- [user-flow-audit.md](user-flow-audit.md) — 2026-06-24 用户流审计
- [layer-audit.md](layer-audit.md) — 分层审计，**状态：标记为 NEVER IMPLEMENTED（2026-06-25）**
- [design-review-report.md](design-review-report.md) — 2026-06-24 CLI 设计审查
- [cli-refactor-notes.md](cli-refactor-notes.md) — 2026-06-24 CLI 重构记录
- [git-db-consistency-gaps.md](git-db-consistency-gaps.md) — 2026-06-24 Git/DB 一致性分析，**全部 gap 已修复**
- [test-coverage-report.md](test-coverage-report.md) — 当前覆盖率报告
