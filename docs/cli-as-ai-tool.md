# CLI as AI Tool — Design

**版本:** 2026-06-25
**状态:** 草案
**依赖:** [product-vision.md](product-vision.md)

---

## 目标

让 Mother（AI agent）能够**可靠地**调用 PeerPedia CLI 命令。不是让 AI 生成 shell 字符串去拼参数——是用 LLM 原生的 function calling 机制，把每条 CLI 命令暴露为一个结构化 tool。

---

## 三层可靠性模型

### Level 1 — Prompt 描述（不用）

把命令格式写在 system prompt 里，AI 自由生成 shell 命令。

```
You can run: peerpedia article publish <id> --scores "orig=4,..."
```

**问题**：AI 会幻觉参数名、忘记 required 字段、拼错分数格式。不可靠。

### Level 2 — Function Calling / Tool Use（采用）

利用 LLM 原生的 tool calling 能力。每条 CLI 命令定义为一个 tool，带 JSON Schema：

```json
{
  "name": "article_publish",
  "description": "Publish an article into the sedimentation pool. Requires self-review scores.",
  "parameters": {
    "type": "object",
    "properties": {
      "article_id": {
        "type": "string",
        "description": "The article ID (UUID or full-id prefix)"
      },
      "scores": {
        "type": "object",
        "properties": {
          "originality":  {"type": "integer", "minimum": 1, "maximum": 5},
          "rigor":        {"type": "integer", "minimum": 1, "maximum": 5},
          "completeness": {"type": "integer", "minimum": 1, "maximum": 5},
          "pedagogy":    {"type": "integer", "minimum": 1, "maximum": 5},
          "impact":       {"type": "integer", "minimum": 1, "maximum": 5}
        },
        "required": ["originality", "rigor", "completeness", "pedagogy", "impact"]
      }
    },
    "required": ["article_id", "scores"]
  }
}
```

AI 不拼 shell 字符串——它输出结构化调用：

```json
{"name": "article_publish", "parameters": {"article_id": "abc123", "scores": {"originality": 4, ...}}}
```

Mother 接收 → 翻译为 `peerpedia article publish abc123 --scores "originality=4,..."` → 执行 CLI → 把 `--json` 输出返回给 AI。

**所有主流 LLM 原生支持（OpenAI function calling、Anthropic tool use）。不要自己造协议。**

### Level 3 — 动态 Tool 注册（后续优化）

35 条命令全部塞进 system prompt 会污染 context window。
LLM 单次对话通常只需要 2-4 条命令。

解决方案：**运行时按需发现**。

```
1. AI 表达意图: "我想发论文"
2. Mother 检索相关命令 → article_publish, article_show, article_list
3. Mother 只注入这 3 个 tool definition 到当前对话
4. AI 调用 article_show 查状态 → 调用 article_publish 发布
```

---

## Tool Schema 生成

### 单一数据源

不从零手写 35 个 schema。**`parser.py` 的 `COMMAND_GROUPS` 表已经是唯一的命令注册中心**——命令名、参数名、类型、help 文本全在那里：

```python
("article", "Article management", [
    ("publish", _cmd_article_publish, [
        (("id",), {"help": "Article ID (or prefix)"}),
        (("--scores",), {"required": True,
                         "help": f'Self-review scores, e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
    ]),
```

写一个 `generate_tool_definitions()` 遍历这张表，输出 Anthropic/OpenAI 格式的 tool schema。命令定义只在一处维护，AI schema 自动同步。

### 需要补充的元数据

当前 parser 的参数定义缺少 AI 需要的几个字段：

| 当前有 | AI 还需要 |
|--------|----------|
| `help` | ✅ 作为 description |
| `required` | ✅ |
| `choices` | 映射为 `enum` |
| — | `type`（目前靠 argparse action 推断） |
| — | 每个 tool 的 **前置条件描述**（"需要登录"、"目标 article 必须 published"） |
| — | 每个 tool 的 **幂等性标注** |
| — | 返回值 schema（tool call result 的结构） |

建议扩展 `COMMAND_GROUPS` 或加一份轻量的 `tool_metadata.json`：

```json
{
  "article_publish": {
    "preconditions": ["authenticated", "is_maintainer", "has_self_review"],
    "idempotent": false,
    "returns": "article_view",
    "side_effects": ["git_commit", "status_change"]
  }
}
```

---

## 错误处理协议

当前 CLI 的错误输出是人类可读的 Rich 面板 + traceback。AI 无法结构化解码。

### 目标协议

所有命令在 `--json` 模式下，success 和 failure 都输出同一结构的 JSON：

```json
// 成功
{"status": "ok", "article_id": "abc123", "new_status": "sedimentation", "commit_hash": "def67890"}

// 失败
{
  "status": "error",
  "error": {
    "code": "NOT_FOUND",
    "entity": "article",
    "identifier": "abc123",
    "message": "Article 'abc123' does not exist"
  }
}
```

### 错误码枚举

| Code | 含义 | AI 的合理反应 |
|------|------|-------------|
| `NOT_FOUND` | 实体不存在 | 检查 ID，尝试搜索 |
| `NOT_AUTHORIZED` | 无权限 | 告知用户原因，停止 |
| `CONFLICT` | 状态冲突（已 fork、已 publish） | 读取当前状态，告知用户 |
| `VALIDATION_ERROR` | 参数格式不对 | 修正参数，重试 |
| `PRECONDITION_FAILED` | 前置条件未满足 | 告知缺少什么条件 |
| `INTERNAL_ERROR` | 意外错误 | 报告错误，建议重试 |

### 实现路径

PeerPedia 已经有语义异常层次（`NotFoundError`、`NotAuthorizedError`、`ConflictError`……）。给每个异常类加一个 `code` 属性，在 `_with_db` 的 except 分支里检查 `--json` flag，输出 JSON 错误而非 `_die`。

---

## Non-Interactive 模式

当前需要交互的命令：

| 命令 | 交互方式 | AI 解决方案 |
|------|---------|------------|
| `account register` | `getpass` 输入密码 | 接受 `--password` flag（已有的安全讨论需要确认） |
| `account login` | `getpass` 输入密码 | 接受 `--password` flag |
| `article edit` | 打开 `$EDITOR` | `--content` + `--message` 绕过编辑器 |
| `article delete` | `[y/N]` 确认 | `--force` 跳过确认 |
| `review reply` | 打开 `$EDITOR` 写回复 | `--content` 绕过编辑器 |

原则：**每个交互操作都有一个 flags-only 的非交互路径**。人类走交互、AI 走 flags。

---

## 实现优先级

| 步骤 | 内容 | 工作量 |
|------|------|--------|
| P0 | `generate_tool_definitions()` — 从 parser 生成 tool schema | 半天 |
| P1 | 错误 JSON 化 — 所有 `--json` 模式返回结构化错误 | 半天 |
| P1 | Non-interactive flags 补齐 — `edit`/`delete`/`reply` 加 flag | 半天 |
| P2 | 前置条件查询 — `--check-prerequisites` / `--dry-run` | 一天 |
| P3 | 动态 tool 注册 — 按需注入 tool definition | 半天 |
| P4 | 返回值 schema 文档化 | 半天 |

---

## 参考

- [product-vision.md](product-vision.md) — 产品愿景
- [architecture.md](architecture.md) — 技术架构
- `peerpedia_core/cli/parser.py` — `COMMAND_GROUPS` 命令注册表
