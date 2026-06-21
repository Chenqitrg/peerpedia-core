# CLI 重构注意事项

本文档记录 `peerpedia_core/cli.py` 中发现的业务逻辑泄漏和防御性编程问题。
重构时逐函数处理，下面按函数列出。

---

## 基础设施函数

### `_resolve_user(db, user_ref)` — [cli.py:215](peerpedia_core/cli.py#L215)

```python
u = get_user(db, user_ref)       # 先当 UUID 查
u = get_user_by_name(db, user_ref)  # 查不到再当用户名查
```

- **不是问题**，这是合理的 UX 设计（用户可以用 ID 也可以用名字）
- 但两个查询有先后顺序，如果用户名恰好是某 UUID 的前缀，会匹配错

### `_parse_scores(scores_str)` — [cli.py:226](peerpedia_core/cli.py#L226)

- 纯工具函数，无问题

### `_open_editor(initial)` — [cli.py:237](peerpedia_core/cli.py#L237)

- 纯 CLI 基础设施，无问题。含临时文件创建、编辑器调用的编排逻辑，适合留在 CLI 层

---

## 账户

### `_cmd_register` — [cli.py:250](peerpedia_core/cli.py#L250)

- 无问题。纯 wiring：解析参数 → `create_user()` → 输出

### `_cmd_whoami` — [cli.py:265](peerpedia_core/cli.py#L265)

- 无问题。占位实现

---

## 文章

### `_cmd_article_create` — [cli.py:276](peerpedia_core/cli.py#L276)

```python
content = args.content or ""
if not content and not args.no_editor:
    content = _open_editor("")
```

- `--publish` 分支在创建后立即调 `publish_article()`，再调 `self_review`。这是 **编排逻辑**，可以接受留在 CLI
- 但 `create + publish` 是一个常见的复合操作，是否值得在 `commands/` 里提供一个 `create_and_publish_article()`？需要权衡

### `_cmd_article_show` — [cli.py:302](peerpedia_core/cli.py#L302) ⚠️ 问题最多

```python
# 问题 1：猜文件扩展名
raw = ""
rp = DEFAULT_ARTICLES_DIR / article.id
for ext in [".md", ".typ"]:          # ← DB 里 article.format 已知，不需要猜
    f = rp / f"article{ext}"
    if f.exists():
        raw = f.read_text()
        break

# 问题 2：冗余 try/except
try:
    from peerpedia_core.storage.compiler import parse_frontmatter
    fm = parse_frontmatter(raw)       # ← 这个函数永远不 raise，返回 {}
    title = fm.get("title", article.title)
    abstract = fm.get("abstract", article.abstract)
except Exception:                     # ← 永远不会执行的分支
    title = article.title
    abstract = article.abstract
```

- DB 里 article 对象有 `format` 字段，直接用 `f"article.{format_ext}"` 构造路径
- `parse_frontmatter` 源码（[compiler.py:96](peerpedia_core/storage/compiler.py#L96)）所有错误路径返回 `{}`，不会 raise。外层 try/except 是死代码
- 文件读取 + frontmatter 解析可以抽成一个 `commands/` 函数，但更可能只修掉上面两点就够了

### `_cmd_article_list` — [cli.py:339](peerpedia_core/cli.py#L339)

```python
articles = list_articles(db, status=args.status or None)
total = count_articles(db, status=args.status or None)  # ← 第二次查询
```

- 两次 DB 查询做同一件事（先查列表，再查总数）。如果 `list_articles` 能直接返回 total，或者前端只截取前 20 条而总数用 `len()` 近似，可以省掉第二次查询
- CLI 显示 "N article(s)" 但只展示前 20 条，count 的语义是"满足条件的总数"而非"当前展示数"，所以确实需要 total。但可以通过一次查询同时拿列表和总数

### `_cmd_article_edit` — [cli.py:352](peerpedia_core/cli.py#L352)

- 无问题

### `_cmd_article_publish` — [cli.py:365](peerpedia_core/cli.py#L365)

- 无问题

### `_cmd_article_delete` — [cli.py:378](peerpedia_core/cli.py#L378)

- `--force` 保护合理，不算防御性

### `_cmd_article_scan` — [cli.py:387](peerpedia_core/cli.py#L387)

- 无问题。但注意 `main()` 启动时也调了同一函数

---

## 评审

### `_cmd_review_submit` — [cli.py:402](peerpedia_core/cli.py#L402)

- 无问题

### `_cmd_review_list` — [cli.py:418](peerpedia_core/cli.py#L418)

- 无问题

---

## Fork / Merge / Bookmark

### `_cmd_fork` — [cli.py:435](peerpedia_core/cli.py#L435)

- 无问题

### `_cmd_merge_propose` — [cli.py:445](peerpedia_core/cli.py#L445)

- 无问题

### `_cmd_merge_accept` — [cli.py:455](peerpedia_core/cli.py#L455)

- 无问题

### `_cmd_bookmark_add` — [cli.py:467](peerpedia_core/cli.py#L467)

- 无问题

### `_cmd_bookmark_list` — [cli.py:474](peerpedia_core/cli.py#L474)

- 无问题

---

## 编译 ⚠️ 业务逻辑泄漏

### `_cmd_compile` — [cli.py:507](peerpedia_core/cli.py#L507)

整段函数是业务逻辑泄漏的重灾区：

```python
def _cmd_compile(args):
    # ① 源文件探测 —— 猜 .md 还是 .typ
    rp = DEFAULT_ARTICLES_DIR / args.id
    source = None
    for ext in [".md", ".typ"]:        # ← DB 有 format 字段不用
        f = rp / f"article{ext}"
        if f.exists():
            source = f
            break
    if source is None:
        _die(...)

    # ② 格式检测 —— detect_format() 已在 compiler.py，但 CLI 自己又做一遍
    fmt = args.format or detect_format(source)

    # ③ 后端选择 —— 根据格式选 TypstBackend 或 MarkdownBackend
    out_dir = rp / "compiled"
    out_dir.mkdir(exist_ok=True)

    if fmt == "typst":
        backend = TypstBackend()
        result = backend.compile(source, out_dir, fmt=args.format or "pdf")
    else:
        backend = MarkdownBackend()
        result = backend.compile(source, out_dir)

    # ④ 输出（这部分才算真正的 CLI 职责）
    if result.success:
        ...
    else:
        _die(...)
```

**应该搬到 `storage/compiler.py`：** ①②③ — 源文件定位、格式检测、后端选择、输出目录创建。

**应该留在 CLI：** ④ — 结果展示。

理想的 CLI 应该是：

```python
def _cmd_compile(args):
    result = compile_article(args.id, format=args.format)
    if result.success:
        _ok(f"Compiled → {result.output_path}")
    else:
        _die(result.error)
```

`compile_article()` 放在 `storage/compiler.py`，负责查找源文件、选后端、执行编译。

---

## 同步

### `_cmd_sync_status` — [cli.py:490](peerpedia_core/cli.py#L490)

- 无问题。纯查询 + 展示

### `_cmd_sync_push` — [cli.py:539](peerpedia_core/cli.py#L539)

```python
pushed = 0
for op in list_all():
    result = sync_push(db, server, op["id"])
    if result.get("synced"):       # ← 防御性 .get()
        pop_pending(op["id"])
        pushed += 1
```

- `result.get("synced")` — 如果 `sync_push` 的返回契约是**一定包含 `synced` 字段**，那 `.get()` 会在 key 缺失时返回 `None`，静默跳过，掩盖 bug。应该用 `result["synced"]` 让它在契约违反时直接抛 KeyError
- 遍历 pending queue 逐条推送的循环是**编排逻辑**，可以考虑放到 `commands/sync.py`

---

## Parser

### `build_parser()` — [cli.py:568](peerpedia_core/cli.py#L568)

- 145 行纯 argparse 样板，无业务逻辑
- 每个子命令 6-8 行的 `p.add_argument(...)` 重复模式
- 没有防御性问题，只有机械长度问题

---

## 穿越模式（跨函数重复问题）

### 每个 handler 里的 `--json` 分支

15 个 handler 全部重复同一个模式：

```python
if args.json:
    _json_out(result)
else:
    _ok(...) / _print_panel(...) / _print_table(...)
```

可以统一为一个输出函数：

```python
def _output(result, rich_formatter, json_formatter=None):
    if args.json:
        _json_out(json_formatter(result) if json_formatter else result)
    else:
        rich_formatter(result)
```

但每个 handler 的展示逻辑不同（有的是 `_ok`，有的是 `_print_panel`，有的是 `_print_table`），统一有代价。至少值得考虑。

### `server` 默认值

两处重复（`_cmd_sync_status` 和 `_cmd_sync_push`）：

```python
server = args.server or os.environ.get("PEERPEDIA_SERVER", "http://localhost:8080")
```

---

## 总结优先级

| 优先级 | 问题 | 位置 |
|--------|------|------|
| **高** | `_cmd_compile` 整段业务逻辑 → `storage/compiler.py` | [cli.py:507](peerpedia_core/cli.py#L507) |
| **高** | `_cmd_article_show` 冗余 try/except（死代码） | [cli.py:319-326](peerpedia_core/cli.py#L319-L326) |
| **中** | `_cmd_article_show` 猜文件扩展名 → 用 DB format | [cli.py:311-317](peerpedia_core/cli.py#L311-L317) |
| **中** | `_cmd_article_list` 两次查询 → 合并 | [cli.py:341-342](peerpedia_core/cli.py#L341-L342) |
| **中** | `_cmd_sync_push` `.get("synced")` → `["synced"]` | [cli.py:551](peerpedia_core/cli.py#L551) |
| **低** | `_cmd_sync_push` 循环编排 → `commands/sync.py` | [cli.py:548-553](peerpedia_core/cli.py#L548-L553) |
| **低** | server 默认值重复 | [cli.py:491](peerpedia_core/cli.py#L491) + [cli.py:541](peerpedia_core/cli.py#L541) |
| **低** | `--json` 分支模式重复 | 遍布全文件 |
| **低** | `build_parser()` 145 行样板 | [cli.py:568](peerpedia_core/cli.py#L568) |
