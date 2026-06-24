# Git/DB 一致性缺口

**日期:** 2026-06-24
**范围:** 所有同时涉及 Git 写入和 DB 写入的命令路径

---

## 核心问题

三个命令在修改已发布文章时存在相同的崩溃窗口：**git 写入成功后、DB `set_sink_start` 执行前**如果进程崩溃，文章在 DB 中保持 `published` 状态但 git 中已有未审查的新内容。完整性检查检测不到，因为没有 `[status]` 标记提交。

---

## 缺口明细

### G1 — `update_article_content`（update.py:71-91）

**场景:** 编辑已发布文章 → `commit_article` 成功（git 有新内容）→ 进程崩溃 → `set_sink_start` 未执行。

**结果:** DB 状态仍为 `published`，但 git 里已有未审查的新内容。`commit_article` 不写 `[status]` 标记，所以 `_read_status_from_git` 返回 None，`_verify_full` 跳过修复。

```
    commit_article(rp, message, ...)     # L71: GIT WRITE — 成功
    a.title = title; a.abstract = ...     # L79: DB WRITE — 成功
    rebuild_article_authors(...)          # L88: DB WRITE — 成功
    if old_status == "published":
        set_sink_start(...)               # L91: DB WRITE — 崩溃点！
    #                                    # 结果: DB 仍是 published，git 有新内容
```

### G2b — `accept_merge`（merge.py:97-110）

**场景:** 合并到已发布文章 → `merge_git_repos` 成功 → 进程崩溃 → `commit_article("[status] sedimentation")` 未执行。

**结果:** 合并提交已在 git 中，但没有 `[status]` 标记。DB 仍为 `published`。`_verify_full` 检测不到。

```
    merge_git_repos(target_repo, fork_repo)  # L97: GIT WRITE — 成功
    rebuild_article_authors(...)              # L104: DB WRITE — 成功
    if was_published:
        commit_article(..., "[status] sedimentation")  # L110: 崩溃点！
        set_sink_start(...)                   # L118: 永远不会到达
    #                                         # 结果: DB 仍是 published，git 有合并内容
```

### G3 — `rollback_article`（rollback.py:68-76）

**场景:** 回滚已发布文章 → `commit_article` 成功 → 进程崩溃 → `set_sink_start` 未执行。

**结果:** 与 G1 相同——DB 保持 `published`，git 已回滚。但 G3 更严重：`rollback_article` 根本**不写** `[status]` 标记（它使用普通 commit message）。即使正常执行完毕，如果 `set_sink_start` 因 DB 错误而失败，也没有 git 标记可检测。

```
    checkout_files(rp, target_hash)     # L57: GIT WRITE (uncommitted)
    commit_article(rp, message)         # L68: GIT WRITE — 不使用 [status] 标记！
    if old_status == "published":
        set_sink_start(...)             # L76: DB WRITE — 崩溃点！
    #                                   # 结果: DB 仍是 published，git 已回滚
```

---

## 完整性修复盲区

### G9 — `_repair_from_git` 不修复 review（integrity.py:101-107）

`_repair_from_git` 在重建评分时从 DB 缓存读取 review，而非从 git 工作树。如果 review 在 git 中但不在 DB 中（例如 `submit_review` 时 git 写入成功后 DB 写入前崩溃），完整性修复声称"全面修复"但遗漏 review。

```python
def _repair_from_git(db, article_id, ...):
    rebuild_article_authors(db, article_id)      # ✅ 修复作者
    _sync_status_from_git(db, article_id, ...)   # ✅ 修复状态
    recompute_article_score(db, article_id)      # ❌ 从 DB 缓存读 review，不从 git 读
    # 缺少: sync_reviews_from_worktree(db, article_id)
```

修复：在 `recompute_article_score` 之前调用 `sync_reviews_from_worktree`。

---

## 其他低严重性缺口

| 缺口 | 文件 | 场景 | 严重性 | 可恢复 |
|------|------|------|--------|--------|
| G4 | `publish.py:67-74` | `commit_article("[status]")` 成功，DB 状态更新前崩溃 | 低 | ✅ `_repair_from_git` 自动修复 |
| G5 | `workflow.py:120-132` | `publish_ready_articles` 循环中第 N 篇的 git 提交成功，DB 更新前崩溃 | 低 | ✅ `_repair_from_git` 自动修复 |
| G6 | `create.py:54-62` | git 提交成功，DB `create_article` 前崩溃 | 低 | 孤儿 git 目录，手动清理 |
| G7 | `delete.py:38-39` | DB 删除成功，`delete_article_repo` 前崩溃 | 低 | 孤儿 git 目录，无查询影响 |
| G8 | `reviews.py:102-117` | git review 提交成功，DB upsert 前崩溃 | 低 | `sync_reviews_from_worktree` 在下次 sync 时修复 |

---

## 修复方案

G1、G2b、G3 的根本原因相同：**git 写入和 DB `set_sink_start` 之间没有原子性保证，且 git 中没有标记让完整性检查发现不一致。**

统一修复：在 `commit_article`（或等效的 git 写入）**之后**、`set_sink_start` **之前**，写一个 `[status] sedimentation` 标记提交。这样即使 DB 写入失败，`_read_status_from_git` 返回 `"sedimentation"`，`_verify_full` 检测到与 DB 的 `"published"` 不匹配 → `_repair_from_git` → `_sync_status_from_git` 自动修复。

具体改动：

1. **`update_article_content`** — 在 `commit_article` 后立即写 `[status] sedimentation`（如果 `old_status == "published"`）
2. **`accept_merge`** — 修正执行顺序：`merge_git_repos` → `commit_article("[status] sedimentation")` → `set_sink_start`
3. **`rollback_article`** — 在 `commit_article` 中使用 `[status] sedimentation` 消息，而非普通消息
4. **`_repair_from_git`** — 在 `recompute_article_score` 之前添加 `sync_reviews_from_worktree` 调用
