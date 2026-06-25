# Fork Design Gap Report — 2026-06-26

## Design Intent vs Implementation

**设计意图**：draft 也应该可以 fork，但只有 maintainer 可以 fork draft。published 则任何人都可以 fork。

**当前实现**：`FORKABLE_STATUSES = {"published", "rejected"}` — draft 完全不能 fork，无论你是谁。

## 差距定位

### 1. 常量定义（唯一需要改的地方）

[`peerpedia_core/policies/articles.py:78`](peerpedia_core/policies/articles.py#L78)：

```python
FORKABLE_STATUSES = {"published", "rejected"}
```

这里**缺少 `"draft"`**。加上 `"draft"` 后，`assert_can_fork_article` 就会允许 fork draft。

### 2. 策略函数缺少 maintainer 检查

[`peerpedia_core/policies/articles.py:328-344`](peerpedia_core/policies/articles.py#L328-L344)：

```python
def assert_can_fork_article(
    article: Article,
    existing_fork: Article | None,
) -> Article:
    if article.status not in FORKABLE_STATUSES:
        raise NotAuthorizedError("Only published articles can be forked")
    if existing_fork is not None:
        raise ConflictError("Already forked this article")
    return article
```

问题：
- 函数签名**没有接收 user 参数**，无法判断 "这个用户是不是 maintainer"
- 错误消息硬编码了 "Only published articles can be forked"
- 即使加上了 `"draft"`，任何人都能 fork draft，不符合设计意图

### 3. 调用方有 user 信息，但没传进去

[`peerpedia_core/commands/articles/fork.py:38-41`](peerpedia_core/commands/articles/fork.py#L38-L41)：

```python
user = require_user(db, user_id)           # user 已经拿到了
original = require_article(db, article_id)
existing_fork = get_article_by_fork_and_author(db, ...)
assert_not_folded(original, ...)
assert_can_fork_article(original, existing_fork)  # 但 user 没传进去
```

`fork_article` 里已经 resolve 了 user，但调用 `assert_can_fork_article` 时没传 user。

### 4. 权限矩阵文档也需要更新

[`peerpedia_core/policies/articles.py:43`](peerpedia_core/policies/articles.py#L43)：

```
| Fork | assert_can_fork_article | Anyone (no dupe) | published |
```

应该改为：

```
| Fork | assert_can_fork_article | Anyone (no dupe) | published, sedimentation |
|      |                         | Maintainer       | draft                    |
```

## 修复方案

### 需要的改动（2 个文件，~10 行）

**A. `policies/articles.py`：**

1. `FORKABLE_STATUSES` 加入 `"draft"`：
   ```python
   FORKABLE_STATUSES = {"draft", "published", "rejected"}
   ```

2. `assert_can_fork_article` 增加 `user_id` 参数，draft 时检查 maintainer：
   ```python
   def assert_can_fork_article(
       article: Article,
       existing_fork: Article | None,
       user_id: str | None = None,
   ) -> Article:
       if article.status == "draft":
           # Only maintainers can fork a draft
           maintainer_ids = get_maintainer_ids(article.id)  # 或传入 session
           if user_id not in maintainer_ids:
               raise NotAuthorizedError(
                   "Only maintainers can fork a draft article. "
                   "Wait for it to be published, or ask a maintainer to fork it."
               )
       elif article.status not in FORKABLE_STATUSES:
           raise NotAuthorizedError(
               f"Articles with status '{article.status}' cannot be forked. "
               "Only draft, published, or rejected articles can be forked."
           )
       # ...
   ```

   或者更简单：在 `fork_article()` 里先检查 maintainer，再调 policy：
   ```python
   # In fork_article(), before assert_can_fork_article:
   if original.status == "draft":
       maintainer_ids = get_maintainer_ids(db, article_id)
       if user_id not in maintainer_ids:
           raise NotAuthorizedError(
               "Only maintainers can fork a draft article."
           )
   ```

3. 更新 docstring 注释（第 335 行 `"published only"`）。

**B. `commands/articles/fork.py`：**

4. 如果改了 `assert_can_fork_article` 的签名，需要同步更新调用：
   ```python
   assert_can_fork_article(original, existing_fork, user_id=user_id)
   ```

### 关于 sedimentation

Sedimentation（审稿池）状态下的文章**不应该**能 fork。审稿期间内容应保持不变，审稿结束后自动变为 published 后才能 fork。这个行为不需要改。

## 验证方式

修复后应能通过以下场景：

```bash
# 1. Draft: maintainer 可以 fork
peerpedia fork Paper2          # Alice 是 maintainer → ✓

# 2. Draft: 非 maintainer 不能 fork（需要两个用户测试）
peerpedia fork Paper2          # Bob 不是 maintainer → ✗

# 3. Published: 任何人可以 fork
peerpedia fork <published-id>  # Bob → ✓

# 4. Sedimentation: 不能 fork（保持不变）
peerpedia fork "UX Test Article"  # → ✗
```
