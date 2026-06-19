# SOT & Policies Matrix — Unified Source-of-Truth Design

## Problem

Git 存内容，DB 存状态。但分工散落在 `commands.py`、`git_backend.py`、多个 `crud_*.py`、`seed.py` 中——没有一张表可查"这个数据归谁管"。导致：

- 新人无法快速理解数据归属
- 改一处要翻多个文件
- `**kwargs` 透传掩盖必填字段缺失（如 `create_article` 的 `title`）
- git/DB 之间无事务保证，漂移风险难发现

policies（权限规则）同样散落为一组断言函数，缺乏可扫描的结构。

## Solution

两张声明式矩阵——SOT 矩阵定义"数据在哪"，Policies 矩阵定义"谁能做什么"。打开文件即文档，运行时硬约束。

## SOT Matrix

### 结构

文件：`peerpedia_core/storage/sot_matrix.py`

```python
# 列含义
READ = "read"        # 允许从哪个后端读（git / db）
WRITE = "write"      # 写入顺序（"git" / "db" / "git→db"）
SOT = "sot"          # 最终权威来源

SOT_MATRIX = {
    # ── Git SOT ──
    "article_body":         {READ: "git",  WRITE: "git",    SOT: "git"},
    "review_content":       {READ: "git",  WRITE: "git",    SOT: "git"},
    "review_scores_file":   {READ: "git",  WRITE: "git→db", SOT: "git"},
    "article_authors":      {READ: "db",   WRITE: "git→db", SOT: "git"},
    "commit_history":       {READ: "git",  WRITE: "git",    SOT: "git"},

    # ── DB SOT ──
    "article_metadata":     {READ: "db",   WRITE: "db",     SOT: "db"},
    "article_status":       {READ: "db",   WRITE: "db",     SOT: "db"},
    "article_score":        {READ: "db",   WRITE: "db",     SOT: "db"},
    "article_compiled":     {READ: "db",   WRITE: "db",     SOT: "db"},
    "review_scores_cache":  {READ: "db",   WRITE: "db",     SOT: "git"},
    "user_profile":         {READ: "db",   WRITE: "db",     SOT: "db"},
    "user_reputation":      {READ: "db",   WRITE: "db",     SOT: "db"},
    "social_graph":         {READ: "db",   WRITE: "db",     SOT: "db"},
    "merge_proposal":       {READ: "db",   WRITE: "db",     SOT: "db"},
    "citation":             {READ: "db",   WRITE: "db",     SOT: "db"},
}
```

### StorageRouter（运行时强制）

文件：`peerpedia_core/storage/router.py`

```python
class StorageRouter:
    def __init__(self, db_session, git_root): ...
    def read(self, entity: str) -> BackendAccessor: ...
    def write(self, entity: str) -> WriteSequence: ...

class SOTViolationError(Exception): ...
```

违规访问直接抛异常，物理上不可能绕过。上层（`commands.py`）通过 Router 读写，不再直接调 `crud_*.py` 或 `git_backend.py`。

## Policies Matrix

### 结构

文件：`peerpedia_core/policies/article_rules.py`

```python
ROLES = ("author", "auth", "anon")

ARTICLE_MATRIX = {
    "read": {
        ("draft",         "author"): True,
        ("sedimentation", "author"): True,
        ("sedimentation", "auth"):   True,
        ("sedimentation", "anon"):   True,
        ("published",     "author"): True,
        ("published",     "auth"):   True,
        ("published",     "anon"):   True,
    },
    "download": {
        ("draft",     "author"): True,
        ("published", "author"): True,
        ("published", "auth"):   True,
        ("published", "anon"):   True,
    },
    "edit": {
        ("draft",     "author"): True,
        ("published", "author"): True,
    },
    "delete": {
        ("draft",     "author"): True,
        ("published", "author"): True,
    },
    "rollback": {
        ("draft",     "author"): True,
        ("published", "author"): True,
    },
    "publish": {
        ("draft", "author"): True,
    },
    "extend_sink": {
        ("sedimentation", "author"): True,
    },
    "fork": {
        ("published", "author"): True,
        ("published", "auth"):   True,
        ("published", "anon"):   True,
    },
    "sync": {
        ("draft",     "author"): True,
        ("published", "author"): True,
    },
}
```

默认规则：矩阵里没显式列出的组合一律返回 `False`。

### 查表引擎

文件：`peerpedia_core/policies/check.py`

```python
def check(action: str, status: str, user: User | None, author_ids: set[str]) -> bool:
    role = _resolve_role(user, author_ids)
    return ARTICLE_MATRIX.get(action, {}).get((status, role), False)

def assert_can(action: str, status: str, user, author_ids):
    if not check(action, status, user, author_ids):
        raise NotAuthorizedError(f"Cannot {action} article in {status}")
```

现有的 `assert_can_*` 函数收缩为一个通用 `assert_can("edit", ...)`。

## File Structure

```
peerpedia_core/
  storage/
    sot_matrix.py           # SOT 矩阵（一张表定义 git/DB 归属）
    router.py               # StorageRouter（运行时强制执行）
    policies/
      article_rules.py      # 文章权限矩阵
      check.py              # 通用查表引擎
    git_backend.py           # 标记为内部模块
    db/
      crud_*.py              # 标记为内部模块
  exceptions.py              # 新增 SOTViolationError
  commands.py                # 改造：全部走 router + 矩阵查表
```

## Migration Plan

**Step 1**：建矩阵，不拆旧代码
- 新建 `sot_matrix.py`、`article_rules.py`、`check.py`
- 旧函数保留，在关键入口加 `_sot_guard()` 只读检查（log 不阻止）
- 目标：矩阵可 review，旧代码照常运行

**Step 2**：commands.py 切到 Router
- 逐个命令函数改为通过 Router 访问后端
- 断言函数改为 `assert_can("edit", ...)`
- 每改一个跑对应测试
- 目标：业务层全部走矩阵

**Step 3**：清理后端暴露面
- `crud_*.py` / `git_backend.py` 对外函数标记为 `_internal`
- 删掉被矩阵覆盖的旧断言函数
- 目标：新代码不可能绕过矩阵

## Backward Compatibility

矩阵是纯数据（无状态、无 IO），Router 是无状态薄层。任一步出问题，把 `commands.py` 里的 import 改回旧模块即可回滚，数据格式不受影响。
