# REPL 设计文档

**日期:** 2026-06-26
**状态:** 设计阶段，待实现
**关联文档:** [cli-ux-improvements.md](cli-ux-improvements.md), [new-user-cli-test-report.md](new-user-cli-test-report.md)

---

## 一、定位

```
CLI --json    → AI agent 的接口    机器消费，结构化，幂等
CLI --rich    → 人类的临时查看      偶尔用，一次性
REPL          → 人类的日常入口     有状态、交互式、温暖
```

REPL 是 PeerPedia 的**默认人机界面**。CLI 不应是人用的。

---

## 二、当前状态

当前 `repl.py` 使用 prompt_toolkit 的 `PromptSession`（单行输入循环），将 flat command 翻译为 CLI handler。能运行但不成熟：

| 功能 | 状态 |
|------|------|
| Flat commands (`create` 而非 `article create`) | ✅ |
| Persistent DB session | ✅ |
| Sticky user (`:user alice`) | ✅ |
| Tab completion | ✅ |
| History file | ✅ |
| 启动 | ❌ `s-enter` 在 prompt_toolkit 3.0.52 不支持 |
| 多行输入（Enter=换行, 提交） | ❌ key binding 坏了 |
| 文章交互选择 | ❌ 不存在 |
| 颜色温暖化 | ❌ 仍用 blue/cyan |
| 上下文感知 | ❌ 每次要打 article ID |

---

## 三、架构

```
┌──────────────────────────────────────────────────┐
│                 REPL 层                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐ │
│  │ TUI views  │  │ Wizards    │  │ Live       │ │
│  │ (panels,   │  │ (guided    │  │ refresh    │ │
│  │  cards,    │  │  create,   │  │ (auto-scan │ │
│  │  split)    │  │  publish)  │  │  timer)    │ │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘ │
│        │               │               │         │
│  ┌─────┴───────────────┴───────────────┴──────┐  │
│  │            Command dispatcher              │  │
│  │  (flat cmd → CLI handler, same as now)     │  │
│  └────────────────────┬───────────────────────┘  │
└───────────────────────┼──────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────┐
│              CLI / Commands 层                    │
│  同一段 handler — CLI 和 REPL 共享               │
└──────────────────────────────────────────────────┘
```

REPL 不重写业务逻辑。所有 handler 复用 CLI 的 `commands/`。REPL 只做三件事：
1. **输入**（键盘导航 → 拼出 args）
2. **输出渲染**（Rich panels → TUI layout）
3. **状态管理**（sticky user/article contexts）

---

## 四、实现分阶段

### Phase 1：修好当前 PromptSession（可立即上线）

**目标：** 让现有 REPL 能启动、能用。

- 修复 `s-enter` → 改为 `c-j`（Ctrl+J）作为提交键
- 更换色板为暖色系（见第六章）
- 所有 flat command 能正确工作
- 异常不崩溃，catch + 显示

### Phase 2：添加上下文状态

**目标：** 不用每次打 ID。

- `:article <ref>` — 设置当前文章上下文
- `:article` — 清除
- 有上下文时，`show`/`publish`/`review submit` 自动用当前文章
- 底部状态栏显示当前上下文：`[Alice] ▸ My First Paper`

### Phase 3：交互式卡片视图（全屏 TUI）

**目标：** 上下键选文章，一个键操作。

- 从 `PromptSession` 升级到 `Application`（全屏布局）
- `list` 输出可选择的文章卡片
- 上下键移动焦点，Enter 查看详情
- 底部显示可用操作：`Enter: view  p: publish  e: edit  r: review`
- 主视图 + 详情分屏布局

### Phase 4：向导 + 高级功能

- `:write` — 分步引导创建文章
- 排行榜交互选择 + follow
- 通知 badges + `:inbox` 交互式查看
- 实时 sedimentation 倒计时条
- 评分 sparkline 趋势图

---

## 五、交互模式

### 命令模式（默认）

类似当前 REPL + Phase 1/2：

```
┌─ PeerPedia ─────────────────────────────────────────────────┐
│                                                              │
│  Alice> show                                                │
│  ╭─ Article ───────────────────────────────────────╮        │
│  │ My First Paper      sedimentation    ★★★★☆      │        │
│  │ ...                                              │        │
│  ╰──────────────────────────────────────────────────╯        │
│                                                              │
│  [dim]▸ My First Paper  |  Alice[/]                         │
└──────────────────────────────────────────────────────────────┘
                                 ↑ 底部状态栏：当前上下文
```

快捷键：
- `Enter` → 换行
- `Ctrl+J` → 提交命令

### 浏览模式（`list` 等命令触发）

Phase 3：

```
┌─ Articles ───────────────────────────────────────────────────┐
│                                                              │
│  ▸ My First Paper        sedimentation  ★★★★☆  4.2         │
│    Draft Paper           draft          —                   │
│    Tensor Networks       published      ★★★★★  5.0         │
│                                                              │
│  Enter: view  p: publish  e: edit  r: review  b: bookmark   │
│  Esc: back                                                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

浏览模式下：
- `↑ ↓` 移动焦点
- `Enter` 查看详情（切换到详情视图）
- 单字母键（`p` `e` `r` `b`）触发对应操作
- `q` / `Esc` 返回
- `/` 搜索过滤

### 详情视图

选中一篇文章后：

```
┌─ My First Paper ─────────────────────────────────────────────┐
│                                                              │
│  Sedimentation  ·  auto-publishes Jul 02                     │
│  ██████░░░░  4/7 days                                       │
│                                                              │
│  originality    ★★★★☆  4/5                                 │
│  rigor          ★★★★☆  4/5                                 │
│  completeness   ★★★☆☆  3/5                                 │
│  pedagogy       ★★★☆☆  3/5                                 │
│  impact         ★★★★☆  4/5                                 │
│                                                              │
│  Authors: Alice · Bob                                        │
│  Reviews: 2                                                  │
│                                                              │
│  [v]iew content  [e]dit  [p]ublish  [r]eview  [b]ack        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 向导模式（`:write`）

```
┌─ New Article ────────────────────────────────────────────────┐
│                                                              │
│  Title: ▌                                                    │
│                                                              │
│  Format: [markdown] typst                                    │
│                                                              │
│  Content (Ctrl+D to finish):                                │
│  ▌                                                           │
│                                                              │
│  [dim]Tab to next field · Ctrl+J to create[/]               │
└──────────────────────────────────────────────────────────────┘
```

---

## 六、色板设计

### 设计原则

- 无蓝色调
- 羊皮纸（淡黄）/ 陶土 / 米色 / 棕色 / 橘色
- Light mode（白天）：parchment 背景
- Dark mode（夜晚）：深木色 / 余烬 / 琥珀

### Light Mode — "Parchment"

```
bg:          #F6F0E6  暖纸底
surface:     #FFFCF7  卡片/面板底色
text:        #1F1B16  正文深棕
primary:     #A85F3B  主色 陶土橙棕
muted:       #6F665E  次要文字 暖灰
border:      #D8CBBB  卡片边框 浅麦色
accent:      #B08A57  高亮 金棕
olive:       #777C5C  橄榄绿（success 替代绿色）

error:       #B84040  砖红（无替代，红色系语义太强）
warning:     #D4893C  琥珀

prompt:      primary (#A85F3B)
separator:   border (#D8CBBB)
selected bg: #EAE0D3  选中态（bg 加深一层）
card bg:     surface (#FFFCF7)
```

### Dark Mode — "Ember"

```
bg:          #1B1A17  深土色底
surface:     #25231F  卡片/面板底色
text:        #EFE8DC  暖光白
primary:     #D18462  余烬玫瑰
muted:       #BDB3A6  暖灰
border:      #454037  深棕边框
sage:        #8F9A82  暖鼠尾草绿（success）
accent:      #B89A66  暗金

error:       #CC5544  余烬红
warning:     #D4A03C  琥珀金

prompt:      primary (#D18462)
separator:   muted (#BDB3A6)
selected bg: #2D2A24  选中态（bg 加深一层）
card bg:     surface (#25231F)
```

### Rich Theme 映射

```python
parchment_theme = Theme({
    "success":  "#777C5C bold",   # olive
    "error":    "#B84040 bold",   # brick red
    "warning":  "#D4893C bold",   # amber
    "info":     "#A85F3B bold",   # primary
    "accent":   "#B08A57 bold",   # gold-brown
    "muted":    "#6F665E dim",    # warm gray
})

ember_theme = Theme({
    "success":  "#8F9A82 bold",   # sage
    "error":    "#CC5544 bold",   # ember red
    "warning":  "#D4A03C bold",   # golden amber
    "info":     "#D18462 bold",   # primary
    "accent":   "#B89A66 bold",   # dark gold
    "muted":    "#BDB3A6 dim",    # warm gray
})
```

### prompt_toolkit 样式

```python
parchment_prompt_style = Style.from_dict({
    "prompt":       "#A85F3B bold",   # primary
    "separator":    "#D8CBBB",        # border
    "status-bar":   "bg:#F6F0E6 #1F1B16",
    "selected":     "bg:#EAE0D3 #1F1B16 bold",
    "card-border":  "#D8CBBB",
})

ember_prompt_style = Style.from_dict({
    "prompt":       "#D18462 bold",   # primary
    "separator":    "#454037",        # border
    "status-bar":   "bg:#1B1A17 #EFE8DC",
    "selected":     "bg:#2D2A24 #EFE8DC bold",
    "card-border":  "#454037",
})
```

### Mode 切换

检测终端背景色（OSC 11 query），自动选择 light/dark。用户可覆盖：

```
:theme light
:theme dark
```

---

## 七、排版系统：Unicode 伪字体

### 设计原则

> **伪字体只负责气氛和层级，不负责承载关键信息。**  
> 原始语义必须保留在普通文本、metadata、或 plain text fallback 中。

核心约束：
- 同一屏幕不超过三种伪字体家族
- 正文和代码永不做伪字体转换
- 状态/错误/警告优先靠颜色和符号表达，伪字体只增强
- 每个渲染函数返回 `{display, plain}` 双版本

### 语义角色 → Unicode Block 映射

| 角色 | Block | 示例 | 说明 |
|------|-------|------|------|
| 标题 | Math Bold Serif `U+1D400` | `𝐌𝐲 𝐏𝐚𝐩𝐞𝐫` | 论文标题的重量感 |
| 副标题/引用 | Math Italic `U+1D434` | `𝐼𝑛 𝑡ℎ𝑖𝑠 𝑝𝑎𝑝𝑒𝑟...` | 短句限定，不超过两行 |
| 作者署名 | Math Script `U+1D49C` | `𝒜𝓁𝒾𝒸𝑒` | 签名感，仅短名字。有缺口需 lookup table |
| 机构/期刊 | Math Fraktur `U+1D504` | `𝔓𝔢𝔢𝔯𝔓𝔢𝔡𝔦𝔞` | 品牌徽章，不用于长机构名。有缺口 |
| 状态标签 | Math Sans Bold `U+1D5D4` | `𝗗𝗥𝗔𝗙𝗧` | 像 badge，醒目 |
| 日期/commit | Math Monospace `U+1D670` | `𝟸𝟶𝟸𝟼-𝟶𝟼-𝟸𝟼` | 数字 `U+1D7F6`，字母 `U+1D670` |
| 评分数字 | Double-Struck `U+1D7D8` | `𝟜.𝟚` | 指标感。注意不是 `U+1D7E2`（那是无衬线数字） |
| 正文 | 普通文本 | `This paper argues...` | 永不做伪字体转换 |
| 代码/命令 | 普通等宽 | `cite("doe2026")` | 可复制、可执行 |

### Block 缺口警告

Script 和 Fraktur block 不是连续映射的。部分字母复用 Letterlike Symbols（`ℬ ℰ ℱ ℋ ℐ ℒ ℳ ℛ` for Script; `ℭ ℌ ℑ ℜ ℨ` for Fraktur）。实现时必须用 lookup table，不能 `base + offset`。

### 视觉层级

**Level 0 — 机器可读层：** 纯 ASCII/Unicode，用于搜索、复制、导出、日志。

**Level 1 — REPL 输出层：** 标题 + 状态 + 评分用伪字体，正文普通。

**Level 2 — 卡片层：**
```
╭─ 𝗗𝗥𝗔𝗙𝗧 ─────────────────────────────╮
│ 𝐌𝐲 𝐏𝐚𝐩𝐞𝐫                           │
│ 𝒜𝓁𝒾𝒸𝑒 · 𝔓𝔢𝔢𝔯𝔓𝔢𝔡𝔦𝔞 𝔏𝔞𝔟              │
│ 𝟸𝟶𝟸𝟼-𝟶𝟼-𝟸𝟼 · 𝚊𝟹𝚏𝟿𝚌𝟸 · score 𝟜.𝟚 │
╰──────────────────────────────────────╯
```

**Level 3 — 出版预览层：** 接近论文首页，居中排版，仅用于 `show --full`。

### 设计禁忌

- ❌ 正文全部转换 → 伤害可读性、搜索、可访问性
- ❌ 装饰承担唯一语义 → `𝗗𝗥𝗔𝗙𝗧` 只是渲染层，metadata 仍用 `"status": "draft"`
- ❌ 代码/命令做伪字体 → 可复制性被破坏，粘贴到 shell 可能炸
- ❌ 一行超过三种伪字体家族 → 像 Unicode 马戏团

### 实现

```python
def render_display(text: str, role: str) -> str:
    """Unicode 伪字体渲染，用于终端视觉输出。"""
    ...

def render_plain(text: str, role: str) -> str:
    """返回原始 ASCII，用于搜索/复制/导出。"""
    ...
```

每处渲染保留 `{display, plain}` 双版本。`--no-unicode` 开关全局禁用伪字体。

---

## 八、状态管理

### 会话上下文

```python
class REPLState:
    user_id: str | None          # sticky user
    article_id: str | None       # current article context
    view: str                    # "command" | "browse" | "detail" | "wizard"
    theme: str                   # "parchment" | "ember"
    last_scan: float             # auto-publish timer
```

### 上下文传递

有 `article_context` 时，命令自动填充 article ID：

```
> :article my first paper        ← 设置上下文
[dim]▸ My First Paper (fb14c5d9)[/]

> publish --scores "orig=4,..."  ← 不用写 article ID
✓ Published fb14c5d9 to sedimentation
```

### 状态栏

底部常驻一行：

```
[dim]▸ My First Paper  |  Alice  |  2 new notifications  |  F1:help[/]
```

---

## 九、Meta 命令扩展

| 命令 | 功能 |
|------|------|
| `:help`, `:h` | 命令参考 |
| `:user <ref>`, `:u` | 设置 sticky user |
| `:article <ref>`, `:a` | 设置当前文章上下文 |
| `:article`, `:a clear` | 清除上下文 |
| `:quit`, `:q` | 退出 |
| `:theme <light\|dark>` | 切换色板 |
| `:feed` | 刷新 feed 视图 |
| `:inbox` | 通知中心（交互式） |
| `:write` | 进入向导模式创建文章 |
| `:school` | 交互式排行榜 |

---

## 十、技术选型

### 为什么从 `PromptSession` 升级到 `Application`

| | PromptSession | Application |
|---|--------------|-------------|
| 布局 | 单行输入 + 上文滚动 | 全屏可分区 |
| 焦点管理 | 只有 input buffer | 多组件自由切换 |
| 键盘事件 | 全局 key binding | 每个组件独立 binding |
| 实时刷新 | 不支持 | `invalidate()` 重绘 |
| 复杂度 | 低（300 行） | 中（~800 行预计） |

**建议：** Phase 1-2 用 PromptSession（够用）。Phase 3 开始用 Application。

### 关键依赖

```
prompt_toolkit >= 3.0.50    # TUI 框架
rich             >= 13       # 富文本渲染
```

### 文件结构

```
peerpedia_core/
  repl/
    __init__.py        # run() 入口 + Application 组装
    state.py           # REPLState dataclass
    theme.py           # parchment/ember 色板
    views/
      browse.py        # 文章列表选择视图
      detail.py        # 文章详情视图
      wizard.py        # 向导模式
      inbox.py         # 通知中心
      status_bar.py    # 底部状态栏
    commands.py        # 命令分发（从当前 repl.py 迁移）
    wizard.py          # 交互式向导
```

---

## 十一、与 CLI 的共享边界

REPL 不应该重复实现 CLI 已经有的东西：

| 层 | 共享方式 |
|----|---------|
| 命令分发 | 保持 `cmd_map` + `parser.parse_args()` 翻译 |
| 输出渲染 | 共享 `cli/display.py` 的 Rich 函数（panel、stars、diff） |
| 色板 | REPL 和 CLI `--rich` 使用同一 theme 定义 |
| 数据 | 复用 commands/ + storage/ 全部函数 |
| 错误 | 复用 `PeerpediaError` 异常体系 |

---

## 十二、成功标准

Phase 1 完成后：
- 新用户可以在 REPL 中完成 "注册 → 写文章 → 发布 → 查看" 全流程
- 不需要打一次 article ID（通过上下文）
- 不需要切换到 CLI

Phase 3 完成后：
- 用户可以用键盘导航完成日常操作
- feed 浏览、文章查看、评审提交都在 REPL 内闭环
- 新用户 5 分钟内能完成第一篇论文的发布
