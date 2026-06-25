# CLI AI-First 重构审计

**日期:** 2026-06-25
**状态:** 锁定 — 新人工程师必须按此文档执行
**前置阅读:** [product-vision.md](product-vision.md) · [cli-as-ai-tool.md](cli-as-ai-tool.md)

---

## 核心原则

> **CLI 的默认消费者是 AI agent，不是人类。人类通过 `--human` opt-in。**

当前状态完全反了：默认输出是 Rich 终端面板（人类专用），`--json` 是 opt-in。AI agent 需要记住在每个命令后加 `--json`、解析自然语言错误消息、面对交互式提示时挂起。

---

## 改动清单（按优先级排序）

### P0 — 阻塞 AI 可用性，必须最先改

#### 1. 反转输出默认值：JSON 是默认，`--human` 是 opt-in

**文件:** `cli/parser.py` `_COMMON_ARGS`

```python
# 改前
_COMMON_ARGS = [
    (("--json",), {"action": "store_true", "help": "Output as JSON"}),
]

# 改后
_COMMON_ARGS = [
    (("--human",), {"action": "store_true", "help": "Human-readable output (Rich formatting, colors, panels)"}),
]
```

**影响:** 所有 30 个 handler 的 `if args.json:` 改为 `if not args.human:`。AI 不传任何 flag 就能获得 JSON，人类传 `--human` 获得 Rich 面板。

#### 2. 结构化错误：`_die` 和 `_with_db` 输出机器可读错误

**文件:** `cli/helpers.py` `_die()`（第 94 行）、`_with_db`（第 29 行）
**依赖:** `exceptions.py` 改造（见第 3 项）

```python
# 改前
def _die(msg: str) -> None:
    console.print(f"✗ [{theme.styles['error']}]{msg}[/]")
    sys.exit(1)

# 改后
def _die(msg: str, code: str = "ERROR", **context) -> None:
    """Exit with an error message.  In AI mode (default) outputs JSON."""
    import json as _json
    error = {"error": code, "detail": msg, **context}
    print(_json.dumps(error))
    sys.exit(1)
```

`_with_db` 的 except 分支同步改造：

```python
# 改前
except Exception as e:
    import traceback
    traceback.print_exc()
    _die(str(e))

# 改后
except PeerpediaError as e:
    _die(e.detail, code=e.code, **e.context)
except Exception as e:
    import traceback
    traceback.print_exc()
    _die(str(e), code="INTERNAL_ERROR")
```

**关键：** 每个 handler 的每个 `_die()` 调用点需要手动 review，加上正确的 `code` 参数。不能批量替换。

#### 3. 异常类加结构化字段

**文件:** `exceptions.py`

每个异常类加 `code` 和上下文属性：

```python
class PeerpediaError(Exception):
    def __init__(self, detail: str, code: str = "ERROR", **context):
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.context = context

class NotFoundError(PeerpediaError):
    def __init__(self, detail: str, resource_type: str = "", resource_id: str = ""):
        super().__init__(detail, code="NOT_FOUND",
                         resource_type=resource_type, resource_id=resource_id)

class NotAuthorizedError(PeerpediaError):
    def __init__(self, detail: str, permission: str = ""):
        super().__init__(detail, code="NOT_AUTHORIZED", permission=permission)

class ConflictError(PeerpediaError):
    def __init__(self, detail: str, conflicting_entity: str = ""):
        super().__init__(detail, code="CONFLICT", conflicting_entity=conflicting_entity)

# ... 其余类推
```

**错误码枚举：**

| code | 含义 | AI 应该做什么 |
|------|------|-------------|
| `NOT_FOUND` | 实体不存在 | 搜索或列举已有实体 |
| `NOT_AUTHORIZED` | 无权限 | 告知用户，不重试 |
| `CONFLICT` | 状态冲突 | 读取当前状态，告知用户 |
| `BAD_REQUEST` | 参数不合法 | 修正参数格式重试 |
| `PRECONDITION_FAILED` | 前置条件未满足 | 补足缺失条件 |
| `TRANSPORT_ERROR` | 网络/协议错误 | 重试或检查 peer 状态 |
| `INTERNAL_ERROR` | 意外错误 | 报告并建议重试 |

#### 4. 所有交互式操作加 non-interactive flag

| 命令 | 阻塞点 | 加什么 flag |
|------|--------|------------|
| `account register` | `getpass.getpass()` | `--password` 改为 `required=True`，移除交互式回退 |
| `account login` | `getpass.getpass()` | 同上 |
| `account recover` | `getpass.getpass()` | 同上 |
| `article create` | `_open_editor()` | 已有 `--content` + `--no-editor`，确认够用 |
| `article edit` | `_prompt_commit_message()` | 加 `--message "commit msg"` 绕过编辑器 |
| `article delete` | `input("[y/N]")` | 加 `--force` 跳过确认 |
| `review reply` | `_open_editor()` | 加 `--content "reply text"` 绕过编辑器 |

**原则：** AI 调 CLI 时不应该有任何 stdin 等待。所有需要人类输入的地方，必须有一个 flag 替代。

#### 5. `_parse_scores` 加验证和结构化报错

**文件:** `cli/helpers.py` 第 233 行

```python
# 改前：裸 ValueError，无维度校验
def _parse_scores(scores_str: str | None) -> dict | None:
    if not scores_str:
        return None
    return {k.strip(): int(v.strip())
            for part in scores_str.split(",")
            for k, v in [part.strip().split("=")]}

# 改后：校验维度名、校验值范围、结构化报错
from peerpedia_core.types.scores import SCORE_DIMENSIONS

def _parse_scores(scores_str: str | None) -> dict | None:
    if not scores_str:
        return None
    result = {}
    for part in scores_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            _die(f"Malformed score: '{part}' — expected key=value",
                 code="BAD_REQUEST", field="scores", bad_value=part)
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        if k not in SCORE_DIMENSIONS:
            _die(f"Unknown dimension: '{k}'. Valid: {', '.join(SCORE_DIMENSIONS)}",
                 code="BAD_REQUEST", field="scores", bad_dimension=k)
        try:
            score = int(v)
        except ValueError:
            _die(f"Score for '{k}' must be an integer, got '{v}'",
                 code="BAD_REQUEST", field=f"scores.{k}", bad_value=v)
        if not 1 <= score <= 5:
            _die(f"Score for '{k}' must be 1-5, got {score}",
                 code="BAD_REQUEST", field=f"scores.{k}", bad_value=score)
        result[k] = score
    return result
```

---

### P1 — AI 可用但不优雅，尽快改

#### 6. 补全三个缺失 `--json` 路径的 handler

**`_cmd_sync_status`** (`cli/handlers/bundle.py` 第 18 行)

```python
# 在函数开头检查
if not getattr(args, "human", False):
    _json_out({"server": server, "online": online, "pending_ops": n})
    return
# 否则渲染 Rich Panel...
```

**`_cmd_compile`** (`cli/handlers/compile_.py` 第 13 行)

```python
if not getattr(args, "human", False):
    _json_out({
        "success": result.success,
        "format": result.format,
        "output_path": str(result.output_path) if result.output_path else None,
        "error": result.error,
    })
    return
# 否则 _ok + _open_file + _page...
```

同时在 non-human 模式下**跳过** `_open_file` 和 `_page` 调用——AI 不需要系统浏览器和分页器。

**`_cmd_mother`** (`cli/handlers/mother.py` 第 45 行)

```python
if not getattr(args, "human", False):
    _json_out({
        "message": "Welcome to PeerPedia. I am Mother, your AI guide.",
        "getting_started": [
            {"command": "account register", "args": {"--name": "<your-name>"}, "description": "Create your identity"},
            {"command": "article create", "args": {"--title": "<title>"}, "description": "Write your first paper"},
        ],
    })
    return
# 否则 Rich Panel...
```

#### 7. `_json_out` 默认紧凑格式

**文件:** `cli/helpers.py` 第 129 行

```python
# 改前
def _json_out(data: dict | list) -> None:
    print(json.dumps(data, indent=2, default=str))

# 改后 — 节省 token，AI 不需要 indent
def _json_out(data: dict | list) -> None:
    print(json.dumps(data, separators=(",", ":"), default=str))
```

#### 8. 处理 `--human` 模式下的 Rich 输出

所有 handler 的条件从 `if args.json:` 改为 `if args.human:`，且人类路径保持现有的 Rich 格式化。

**需要触及的文件（按 handler 数）：**
- `cli/handlers/articles.py` — 6 个 handler
- `cli/handlers/social.py` — 12 个 handler
- `cli/handlers/account.py` — 5 个 handler
- `cli/handlers/reviews.py` — 3 个 handler
- `cli/handlers/maintainers.py` — 5 个 handler
- `cli/handlers/notifications.py` — 2 个 handler
- `cli/handlers/bundle.py` — 3 个 handler
- `cli/handlers/compile_.py` — 1 个 handler
- `cli/handlers/mother.py` — 1 个 handler
- `cli/helpers.py` — `_die`, `_ok`, `_json_out`, `_with_db`, `_parse_scores`

---

### P2 — 增强 AI 自主恢复能力

#### 9. 每个命令的返回值加 `action` 字段

AI 需要知道"这个操作做了什么"才能决定下一步。在每条 `--json` 输出中加 `action` 字段：

```json
// article publish 成功
{"action": "article_published", "article_id": "abc123", "new_status": "sedimentation"}

// bookmark add 成功
{"action": "bookmark_added", "article_id": "abc123"}

// maintainer remove 成功
{"action": "maintainer_removed", "article_id": "abc123", "removed_user_id": "xyz"}
```

`action` 是一个枚举字符串，统一定义。AI 可以根据 `action` 值做路由判断，不需要解析整个返回体。

#### 10. 错误消息带 `suggestion`

每个 `_die` 调用加上可操作的修复建议：

```python
_die("Article not found",
     code="NOT_FOUND",
     resource_type="article",
     resource_id=article_id,
     suggestion="Check the article ID with 'article list --mine' or try a shorter prefix")
```

AI 可以把 `suggestion` 直接展示给用户，或者自动执行建议的操作。

#### 11. `_page` 和 `_open_file` 在 non-TTY 下的行为

**文件:** `cli/helpers.py` 第 64、79 行

```python
def _page(text: str) -> None:
    if not sys.stdin.isatty():
        print(text)  # 直接输出，不启动分页器
        return
    # 原有分页器逻辑...

def _open_file(path: str) -> None:
    if not sys.stdin.isatty():
        return  # AI 模式下静默跳过
    # 原有 open/xdg-open 逻辑...
```

---

### P3 — 文档和约定

#### 12. 返回值 schema 文档

每个 handler 的 `--json` 输出必须有文档化的 schema。放在 handler 函数的 docstring 里：

```python
def _cmd_article_publish(db, args):
    """Publish an article into the sedimentation pool.

    Returns (JSON):
        {"action": "article_published", "article_id": str, "new_status": "sedimentation",
         "commit_hash": str, "sink_start": str}

    Errors:
        NOT_FOUND — article does not exist
        NOT_AUTHORIZED — caller is not a maintainer
        PRECONDITION_FAILED — missing self-review scores
        CONFLICT — article already in sedimentation
    """
```

#### 13. 新 handler 检查清单

新增 CLI handler 时必须满足：

- [ ] 默认输出 JSON（`if args.human:` 才走 Rich）
- [ ] 所有 `_die` 调用带 `code` 参数
- [ ] 所有交互式操作有对应的 non-interactive flag
- [ ] 返回值有 `action` 字段
- [ ] docstring 包含 JSON 输出 schema 和错误码
- [ ] 在 non-TTY 环境下不启动编辑器/分页器/浏览器

---

## 改动量估算

| 优先级 | 涉及文件 | 行数估算 | 风险 |
|--------|---------|---------|------|
| P0 | exceptions.py, helpers.py, parser.py, 10 个 handler 文件 | ~200 行 | 中：需要 review 每个 `_die` 调用点 |
| P1 | helpers.py, bundle.py, compile_.py, mother.py | ~100 行 | 低 |
| P2 | helpers.py, 所有 handler | ~150 行 | 低 |
| P3 | 文档 | 0 行新代码 | 无 |

**总计 ~450 行改动，P0 约 2 天，P1+P2 约 2 天，P3 约半天。**

---

## 不需要改的

以下模块和行为**不变**：

- `storage/` — 零改动
- `commands/` — 零改动（业务逻辑不变）
- `transport/` — 零改动
- `bundle/`、`social/`、`workflow/` — 零改动
- `types/scores.py` — 零改动（`SCORE_DIMENSIONS` 已存在，`_parse_scores` 引用它即可）
- 现有的 `--json` 测试用例 — 行为不变，只是 flag 名从 `--json` 变为去掉 flag

---

## 参考

- [product-vision.md](product-vision.md) — 产品愿景和四视图架构
- [cli-as-ai-tool.md](cli-as-ai-tool.md) — CLI 作为 AI tool 的设计方案
- [architecture.md](architecture.md) — 分层架构约束
