# Review 文件阅读顺序

## 总原则

**Git 是内容真相源（SOT），DB 是元数据缓存。** 评审文件（scores.json、threads/*.md）先写入 git，再缓存到 DB。

## 建议阅读顺序

### Phase 1 — 核心概念
1. [README.md](../README.md) — 项目概览 + 5 分钟上手
2. [architecture.md](architecture.md) — 完整文件树和分层规则
3. `peerpedia_core/exceptions.py` — 语义异常定义
4. `peerpedia_core/types/scores.py` — 评分维度
5. `peerpedia_core/config/paths.py` — 数据目录布局

### Phase 2 — 存储层
6. `peerpedia_core/storage/db/models.py` — ORM 模型
7. `peerpedia_core/storage/db/engine.py` — 引擎 + 迁移 + JSONList/JSONDict
8. `peerpedia_core/storage/git_backend.py` — Git 操作（init、commit、diff、merge）
9. `peerpedia_core/storage/db/crud_user.py` — User + Follow CRUD
10. `peerpedia_core/storage/db/crud_article.py` — Article CRUD

### Phase 3 — 业务逻辑
11. `peerpedia_core/policies/articles.py` — 权限检查
12. `peerpedia_core/commands/` — 编排层（articles/、reviews.py、merge.py、maintainers.py）
13. `peerpedia_core/workflow/scoring.py` — 评分聚合
14. `peerpedia_core/workflow/reputation.py` — 声誉计算

### Phase 4 — 网络层
15. `peerpedia_core/transport/http_server.py` — HTTP 服务器
16. `peerpedia_core/transport/http_client.py` — HTTP 客户端
17. `peerpedia_core/transport/auth.py` — Ed25519 认证
18. `peerpedia_core/bundle/client.py` — P2P 同步协议

### Phase 5 — CLI
19. `peerpedia_core/cli/parser.py` — 命令表 + argparse
20. `peerpedia_core/cli/helpers.py` — 共享工具（session、editor、DB）
21. `peerpedia_core/cli/handlers/` — 命令实现

### Historical Docs
- [user-flow-audit.md](user-flow-audit.md) — 2026-06-24 用户流审计，记录当时的 TODO 状态
- [layer-audit.md](layer-audit.md) — 分层审计，架构约束已通过 `test_architecture.py` 强制执行
- [design-review-report.md](design-review-report.md) — 2026-06-24 设计审查，多数问题已修复
- [cli-refactor-notes.md](cli-refactor-notes.md) — 2026-06-24 CLI 重构记录
- [git-db-consistency-gaps.md](git-db-consistency-gaps.md) — 2026-06-24 Git/DB 一致性分析
- [test-coverage-report.md](test-coverage-report.md) — 当前覆盖率报告
