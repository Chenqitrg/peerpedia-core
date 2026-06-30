# REPL Redesign — Interactive Page Browser

## Context

当前 REPL 有几个核心问题：
1. `:user`/`:article` 设置上下文但从不生效（死数据）
2. `browse.py` 的交互浏览器写好了但从未被调用（死代码）
3. 输出是一次性表格，没有导航和交互
4. 补全机制简陋，不能像 fish/zsh 那样展示候选项

目标：将 REPL 从"命令行模拟器"变成**全屏交互式页面浏览器**。

## Architecture

REPL 分两种模式：

**命令模式**（页面栈空）：输入行接受命令（`new`、`mine`、`feed`、`school`、`user Marie`），回车进入对应页面。补全激活。

**页面模式**（页面栈非空）：输入行变为过滤框，直接打字实时过滤当前页面 panel 列表。不执行命令。Esc 退出页面后回到命令模式。

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
│  peerpedia > 搜索文本                       │  ← 命令模式=命令；页面模式=过滤
│  ── article create    article delete        │  ← 补全下拉（仅命令模式）
│      article edit     article list          │
└─────────────────────────────────────────────┘
```

- 单一 `prompt_toolkit.Application`，内部维护页面栈
- `Enter` → push 新页面，`Esc` → pop 回上层（恢复之前的聚焦位置）
- 从命令模式重新进入页面 → 全新页面，不恢复之前的位置和滚动状态
- 补全：fish/zsh 风格下拉列表，Tab 展示所有匹配项（仅命令模式）

## 命令体系

**所有命令统一，无 `:` 前缀。** 原先的 meta 命令（`:user`、`:school`、`:write`、`:inbox`）现在和 `article list` 同级，都是普通命令。`:` 仅保留**页面模式**下的 `:edit`（编辑器打开自己的文章，仅在聚焦 Article Panel 时有效）。

| 命令 | 效果 |
|------|------|
| `new` | 新建文章：打开编辑器写内容，关闭后 prompt 输标题 |
| `mine` | 我的文章 ArticleList |
| `feed` | 我关注的人的文章 ArticleList |
| `school` | 排行榜 |
| `user <name>` | 用户主页 |
| `inbox` | 通知列表，`Enter` 跳转到关联页面 |
| `editor` | 显示当前编辑器路径 |
| `editor <path>` | 设定编辑器路径 |
| `theme dark` / `light` | 切换主题 |
| `quit` | 退出 REPL |

完整形式（`article list`、`article create` 等）保留作为 fallback，补全下拉也列出来。

## Page Stack

```
article list ──→ ArticleList
                  Enter → ReviewList
                  :h → History
                          Enter → Diff（与父 commit 对比）
  
ReviewList
  Enter → ThreadView
            Enter → 编译 HTML（该条消息 Markdown）
  Tab → reviewer 名字 → Enter → UserProfile

school ──→ School
            Enter → UserProfile
user <name> ──→ UserProfile
                  Enter article → ReviewList → ...
```

## Panel Types

### Article Panel（已有组件 `article_meta_panel`）
- 标题、作者、状态 badge、分数、摘要
- 焦点态：左侧一条垂直高亮竖线（VS Code indent guide 风格）
- `Enter` → 进入 ReviewList
- `:history` → 历史页面
- `:edit` → 编辑器打开（仅自己的文章）
- `:publish` → 发布（仅自己的 draft）
- `:review` → 提交审查：编辑器写评论，退出时打分（仅他人的文章）
- `:bookmark` → bookmark / unbookmark（toggle）
- `:fork` → fork（仅对他人的文章）
- `:share` → 分享文章
- `Delete` → 弹出确认 "Delete this article? [y/N]"，`y` 确认删除（仅自己的 draft）

### User Panel（已有组件 `display_user`）
- 用户名、ID、affiliation、reputation、follow 状态
- `Enter` → 进入 UserProfile
- `:follow` → follow / unfollow（toggle）

### Review Panel（新）
- 分数 bars、reviewer 名字（可聚焦，underline 样式）
- thread[0] 前 400 字预览
- 两个可聚焦子区域，`Tab` 交替切换：
  - panel 主体：`Enter` 进入 ThreadView
  - reviewer 名字：`Enter` 进入 UserProfile
- 底部 dim 提示 "Enter: thread   Tab: reviewer"

### Thread View（新）
- 多条消息 panel，左侧竖线串联，暗示对话关系
- 每条消息：作者、时间戳、内容
- `↑↓` 聚焦消息，`Enter` → 编译该条消息的 Markdown（系统浏览器打开）

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
- **输入歧义处理**：页面模式下 `:` 开头的字符序列为页面内操作。其余所有字符视为过滤文本。`?` 由 prompt 吸收，不进入过滤。

## 交互

| 按键 | 模式 | 行为 |
|------|------|------|
| `↑` `↓` | 页面 | 聚焦上一个/下一个 panel |
| 鼠标悬停 | 页面 | 自动聚焦到光标下方的 panel |
| 鼠标点击 | 页面 | 点击 panel → 聚焦；点击 reviewer 名字 → 跳转 UserProfile |
| `Enter` | 页面 | 进入聚焦项（push 页面） |
| `Esc` | 页面 | 返回上一层（pop 页面，恢复之前的聚焦位置） |
| `Tab` | 页面 | Review Panel 内切换子聚焦区域 |
| `:edit` | 页面 | 编辑器打开（仅聚焦自己的 Article Panel） |
| `:publish` | 页面 | 发布（仅聚焦自己的 draft Article Panel） |
| `:history` | 页面 | 历史页面（仅聚焦 Article Panel） |
| `:review` | 页面 | 提交审查：编辑器写评论，退出时打分（仅聚焦 Article Panel） |
| `:bookmark` | 页面 | bookmark/unbookmark toggle（仅聚焦 Article Panel） |
| `:fork` | 页面 | fork 文章（仅聚焦 Article Panel） |
| `:share` | 页面 | 分享文章（仅聚焦 Article Panel） |
| `:follow` | 页面 | follow/unfollow toggle（仅聚焦 User Panel） |
| `Delete` | 页面 | 删除文章，弹出确认 `[y/N]`（仅聚焦自己的 draft Article Panel） |
| 直接打字 | 页面 | 实时过滤当前列表 |
| 直接打字 | 命令 | 输入命令，Enter 执行 |
| `?` | 命令 | prompt 变为 mother 模式 |

## What Gets Removed

- `:unicode` meta 命令（从未实现）— 从 help 文档中删除
- `dispatch.py` `_META_DISPATCH` 字典和所有 `_handle_*` 函数 — 不再有 `:` 前缀命令
- `meta.py` 中 `:user`/`:article` 的"设置上下文"逻辑 — 改为直接跳转页面
- `browse.py` `ListBrowser` — 被新的页面架构替代
- `display.py` 一次性输出函数 — 被页面渲染替代
- `wizards.py` — `article create` 改为直接打开编辑器
- 死代码：`browse._browse_articles()`、`browse._browse_reviews()`

## What Gets Reused

- `ArticleMetaPanel`、`DisplayUser` — 现有组件直接嵌入
- `completer.py` — 扩展现有 `ReplCompleter` 为下拉风格
- `state.py` `ReplSession` — 保留 session 管理（去掉 `user`/`article_id` 死字段）
- `engine.py` `_parse_args`、`_resolve_spec` — 保留命令解析
- `wizards.py` — 废弃，`article create` 直接打开编辑器
- `meta.py` `_show_inbox` — 保留通知
- Theme 系统 — parchment/ember 切换
