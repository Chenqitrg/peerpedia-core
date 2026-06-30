# REPL Redesign — Interactive Page Browser

## Context

当前 REPL 有几个核心问题：
1. `:user`/`:article` 设置上下文但从不生效（死数据）
2. `browse.py` 的交互浏览器写好了但从未被调用（死代码）
3. 输出是一次性表格，没有导航和交互
4. 补全机制简陋，不能像 fish/zsh 那样展示候选项

目标：将 REPL 从"命令行模拟器"变成**全屏交互式页面浏览器**。

## Architecture

```
┌─────────────────────────────────────────────┐
│  Page Stack (prompt_toolkit Application)    │
│  ┌───────────────────────────────────────┐  │
│  │  ThreadView                           │  │  ← 栈顶
│  │  [msg1]───[msg2]───[msg3]            │  │
│  ├───────────────────────────────────────┤  │
│  │  ReviewList                           │  │
│  │  [★4.2] [★3.8] [★4.5]               │  │
│  ├───────────────────────────────────────┤  │
│  │  ArticleList                          │  │
│  │  [panel] [panel] [panel]             │  │  ← 栈底
│  └───────────────────────────────────────┘  │
│  ─────────────────────────────────────────  │
│  peerpedia > article list                   │  ← 命令/过滤输入行
│  ── article create    article delete        │  ← 补全下拉
│      article edit     article list          │
└─────────────────────────────────────────────┘
```

- 单一 `prompt_toolkit.Application`，内部维护页面栈
- `Enter` → push 新页面，`Esc` → pop 回上层
- 底部保留命令输入行，输入命令 → 跳转页面；页面激活时直接打字 → 过滤
- 补全：fish/zsh 风格下拉列表，Tab 展示所有匹配项

## 命令体系

**所有命令统一，无 `:` 前缀。** 原先的 meta 命令（`:user`、`:school`、`:write`、`:inbox`）现在和 `article list` 同级，都是普通命令。`:` 仅保留在**页面内单键操作**（Vim 风格）：`:q` 退出当前页、`:e` 编辑器打开自己的文章。

| 命令 | 效果 |
|------|------|
| `article list` | ArticleList 页面 |
| `article create` | 创建向导（原 `:write`） |
| `school` | School 排行页面 |
| `user <name>` | UserProfile 页面 |
| `inbox` | 通知列表 |
| `theme dark` / `theme light` | 切换主题 |
| `quit` | 退出 REPL |

## Page Stack

```
article list ──→ ArticleList
                  Enter → ReviewList
                            Enter → ThreadView
                                      Enter → 编译 HTML
                            Enter reviewer → UserProfile
school ──→ School
            Enter → UserProfile
user <name> ──→ UserProfile
                  Enter article → ArticleList → ...
```

## Panel Types

### Article Panel（已有组件 `article_meta_panel`）
- 标题、作者、状态 badge、分数、摘要
- 焦点态：左侧一条垂直高亮竖线（VS Code indent guide 风格）
- `:e` → 编辑器打开（仅自己的文章）
- `Enter` → 进入 ReviewList

### User Panel（已有组件 `display_user`）
- 用户名、ID、affiliation、reputation
- `Enter` → 进入 UserProfile

### Review Panel（新）
- 分数 bars、reviewer id/name
- thread[0] 前 400 字预览
- 底部 dim 提示 "▾ Enter to expand thread"
- `Enter` → 进入 ThreadView

### Thread View（新）
- 多条消息 panel，左侧竖线串联，暗示对话关系
- 每条消息：作者、时间戳、内容
- `Enter` → 编译 HTML

### User Profile（新）
- 顶：User Panel
- 中：该用户所有非 draft 的 Article Panel 列表（纵向排列，可聚焦）
- 底：可展开的 followers / following 列表（User Panel 列表）
- 所有子列表都可上下聚焦、Enter 进入

## Input

### Prompt

```
peerpedia >                     ← 默认模式
    ↑ 全小写，两个 p 对等

peerpedia > ?                   ← 用户打了 ?
mother >                        ← prompt 吸收 ?，变为 dim 色
  press ? for help              ← dim 提示

mother > help                   ← 输出彩蛋（mother.txt）
```

- 打 `?` → prompt 变为 `mother >`（dim 颜色），下方提示 "press ? for help"
- 删 `?` → 恢复 `peerpedia >`
- `mother > help` → 输出 mother.txt 内容

### 补全

- Tab → 在输入行下方垂直列出所有匹配项（fish/zsh 风格）
- 静态词：所有 command group + action + flags + 新统一命令（`user`、`school`、`inbox`、`write`、`theme`、`quit`）
- 动态词：article ID、@username、user ID

### 过滤

- 在页面栈激活时，直接打字 → 实时过滤当前列表的 panel
- 匹配规则：panel 内任意文本字段包含输入字符（case-insensitive）
- **输入歧义处理**：`:` 前缀仅保留 `:q`、`:e` 两个页面内单键操作。其余所有字符视为过滤文本。`?` 由 prompt 吸收，不进入过滤。

## 交互

| 按键 | 行为 |
|------|------|
| `↑` `↓` | 聚焦上一个/下一个 panel |
| `Enter` | 进入聚焦项（push 页面） |
| `Esc` | 返回上一层（pop 页面） |
| `:q` | 退出当前页（页面内操作） |
| `:e` | 编辑器打开自己的文章（页面内操作，仅 Article Panel） |
| 直接打字 | 实时过滤当前列表 |
| `?` | prompt 变为 mother 模式 |

## What Gets Removed

- `:unicode` meta 命令（从未实现）— 从 help 文档中删除
- `dispatch.py` `_META_DISPATCH` 字典和所有 `_handle_*` 函数 — 不再有 `:` 前缀命令
- `meta.py` 中 `:user`/`:article` 的"设置上下文"逻辑 — 改为直接跳转页面
- `browse.py` `ListBrowser` — 被新的页面架构替代
- `display.py` 一次性输出函数 — 被页面渲染替代
- 死代码：`browse._browse_articles()`、`browse._browse_reviews()`

## What Gets Reused

- `ArticleMetaPanel`、`DisplayUser` — 现有组件直接嵌入
- `completer.py` — 扩展现有 `ReplCompleter` 为下拉风格
- `state.py` `ReplSession` — 保留 session 管理（去掉 `user`/`article_id` 死字段）
- `engine.py` `_parse_args`、`_resolve_spec` — 保留命令解析
- `wizards.py` `_meta_write` — 保留创建向导（重命名为 `article create` 的 REPL 实现）
- `meta.py` `_show_inbox` — 保留通知
- Theme 系统 — parchment/ember 切换
