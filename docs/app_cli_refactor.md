下面这段可以直接给 DeepSeekV4，当作项目重构手册 / 架构判断准则。

---

# PeerPedia Core 架构判断手册：不要再把东西堆进 CLI

你正在协助重构 PeerPedia Core。  
最重要的原则是：

> **不要看到 CLI 报错就直接往 CLI handler 里加逻辑。先判断这段逻辑属于哪一层。**

PeerPedia 的目标分层是：

```text
CLI / REPL / server / scripts
        ↓
      app
        ↓
      core
        ↓
storage / content repo / compute / rules / crypto / transport
```

每层职责不同。

---

# 1. 每层负责什么

## 1.1 CLI 层

CLI 只负责命令行交互：

```text
argparse
--json / --rich
stdout / stderr
exit code
help text
Rich 表格
TTY 检查
打开 $EDITOR
读取用户输入
把 AppResult 渲染成人类可读输出
```

CLI 不应该负责：

```text
业务规则
权限判断
short id 解析
数据库 CRUD
网络同步编排
状态转移
score 规则
review/fork/merge 逻辑
```

CLI 可以有：

```python
prompt_commit_message()
render_result()
parse_argv()
```

CLI 不应该有：

```python
publish_article_business_logic()
sync_all_peers()
validate_review_state()
insert_user_row()
```

---

## 1.2 REPL 层

REPL 是交互 shell。

它只负责：

```text
读取一行命令
维护当前浏览上下文
调用 app command
渲染结果
少量 REPL-only meta command：help/exit/clear/use/status
```

REPL 不应该直接调用：

```text
storage
transport
core.sync
server
CLI helpers
```

目标关系是：

```text
CLI  -> app.commands
REPL -> app.commands
```

而不是：

```text
REPL -> CLI helpers -> core/storage/transport
```

---

## 1.3 app 层

app 层是最容易被忽略的一层。

它负责：

```text
把用户意图变成一次完整用例
```

例如用户说：

```bash
peerpedia article publish abc123
```

app 层负责：

```text
当前用户是谁？
abc123 解析成哪个 article_id？
有没有权限？
是否 experimental？
调用哪个 core 函数？
是否需要 reconcile？
成功返回什么结构化结果？
失败抛什么 AppError？
```

app 层可以做：

```text
AppContext
AppResult
AppError
RefResolver
permission gate
transaction boundary
调用多个 core 函数
把底层异常翻译成用户可理解错误
```

app 层不应该做：

```text
Rich print
argparse
sys.exit
FastAPI Response
SQL 细节
content repo commit 细节
score 数学计算细节
```

app 层可能比较厚，但它厚在“用例编排”，不是厚在“业务规则”。

---

## 1.4 core 层

core 层负责 PeerPedia 的领域动作：

```text
publish article
submit review
fork article
accept merge
invite reviewer
reconcile score
delete article
```

core 回答的问题是：

```text
这个领域动作本身如何成立？
状态如何变化？
哪些领域规则要执行？
需要调用哪些 storage/compute/rules？
```

core 可以长这样：

```python
def publish_article(db, article_id, user_id, self_review):
    ...
```

core 不应该知道：

```text
argparse
Rich
REPL
HTTP request
sys.exit
_out()
```

---

## 1.5 storage 层

storage 负责数据如何读写：

```text
SQLite CRUD
content repo 操作
locks
peer records
bundle bytes
models
sessions
```

storage 不应该知道：

```text
CLI
REPL
app command
Rich
用户消息 code
```

---

## 1.6 rules / compute 层

rules / compute 尽量纯。

它们负责：

```text
score 聚合
reputation
sedimentation
状态规则
review 维度合法性
monotonic search
BFS
```

不应该依赖：

```text
CLI
REPL
server
transport
storage 细节
```

---

## 1.7 transport / server 层

transport 负责传输：

```text
HTTP client
auth header
remote peer
push/pull bundle
network errors
```

server 负责 HTTP 入口：

```text
route
request body
response status
auth middleware
rate limit
```

server 应该调用 app command，而不是自己实现业务流程。

---

# 2. 依赖方向规则

目标依赖方向：

```text
cli/repl/server
    -> app
        -> core
            -> storage / compute / rules
        -> transport interface
        -> crypto/config/types
```

禁止反向依赖：

```text
core 不能 import cli/repl/server
app 不能 import cli/repl/server
storage 不能 import app/cli/repl/server
rules/compute 不能 import cli/repl/server/transport
```

尤其禁止：

```python
from peerpedia_core.cli.msgs import _out
```

出现在：

```text
app
core
storage
rules
compute
transport
```

---

# 3. 判断代码应该放哪一层

看到一个函数时，按下面判断。

---

## 3.1 如果它依赖 TTY/editor/stdout，放 CLI

例如：

```python
def prompt_commit_message(diff: str) -> str:
    if not sys.stdin.isatty():
        ...
    editor = os.environ.get("EDITOR", "vim")
    subprocess.call([editor, temp_file])
```

这属于 CLI。

因为它处理的是：

```text
用户如何输入 commit message
```

不是领域逻辑。

但它不应该直接 `_out()` 或 `sys.exit()`。  
应该：

```python
raise CliInputError("NO_TTY_EDITOR")
```

由 CLI 最外层渲染。

---

## 3.2 如果它解析用户输入为 use-case input，放 app/parsers 或 app/refs

例如：

```python
def parse_scores_arg("orig=4,rigor=5") -> dict[str, int]:
    ...
```

这不应该留在 CLI，因为 REPL/server/scripts 也可能需要。

推荐：

```text
app/parsers.py
types/scores.py
rules/reviews.py
```

拆分原则：

```text
字符串解析格式         -> app/parsers.py
score 维度与范围规则   -> types/scores.py 或 rules/reviews.py
```

---

## 3.3 如果它执行完整用户用例，放 app

例如：

```python
def publish_article_cmd(ctx, inp):
    user_id = require_user(ctx)
    article_id = resolve_article_ref(ctx, inp.article_ref)
    article = core_publish_article(ctx.db, article_id, user_id, inp.self_review)
    return AppResult(...)
```

这属于 app。

因为它做了：

```text
用户身份
ref 解析
调用 core
整理结果
```

---

## 3.4 如果它是领域动作，放 core

例如：

```python
def submit_review(db, article_id, reviewer_id, scores):
    ...
```

这属于 core。

因为它回答：

```text
提交 review 这个动作如何改变系统状态？
```

---

## 3.5 如果它是网络同步编排，放 app/sync，不要放 core

例如：

```python
def sync_all_peers(db, transport, user_id):
    for server in get_known_peers():
        if not transport.is_online(server):
            ...
        sync_all(...)
        discover_articles(...)
```

这属于：

```text
app/sync.py
```

或：

```text
app/commands/sync.py
```

不属于 core。

因为它包含：

```text
peer 遍历
network errors
server URL
clock skew
best-effort policy
progress callback
```

这些是应用级编排，不是领域核心。

---

# 4. app 层标准形态

新增或维护这些模块：

```text
peerpedia_core/app/
  __init__.py
  context.py
  result.py
  errors.py
  refs.py
  parsers.py
  commands/
    article.py
    review.py
    account.py
    fork.py
    merge.py
    bundle.py
    sync.py
```

---

## 4.1 AppContext

```python
@dataclass
class AppContext:
    workspace: Path
    db: Any
    current_user_id: str | None
    repo_root: Path | None = None
    params: Any | None = None
    signing_key_bytes: bytes | None = None
    pubkey_hex: str | None = None
    transport: Any | None = None
    experimental: bool = False
```

CLI/REPL/server 构造 context。  
app command 使用 context。  
core 不需要知道 CLI/REPL/server。

---

## 4.2 AppResult

```python
@dataclass(frozen=True)
class AppNotice:
    code: str
    params: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    notices: list[AppNotice] = field(default_factory=list)
```

app command 返回：

```python
return AppResult(
    code="ARTICLE_CREATED",
    data={"article_id": article_id, "title": title},
    params={"id_short": article_id[:8], "title": title},
)
```

不要在 app command 里 print。

---

## 4.3 AppError

```python
class AppError(Exception):
    code = "ERROR"
    exit_code = 1

    def __init__(self, **params):
        super().__init__(self.code)
        self.params = params
        self.data = {}


class NotFound(AppError):
    code = "NOT_FOUND"
    exit_code = 2


class Unauthorized(AppError):
    code = "UNAUTHORIZED"
    exit_code = 5


class ValidationFailed(AppError):
    code = "VALIDATION_FAILED"
    exit_code = 4
```

app 层抛 `AppError`。  
CLI/REPL/server 负责渲染。

---

## 4.4 RefResolver

```python
def resolve_article_ref(ctx: AppContext, ref: str) -> str:
    ...

def resolve_user_ref(ctx: AppContext, ref: str) -> str:
    ...

def resolve_review_ref(ctx: AppContext, article_id: str, ref: str) -> str:
    ...

def resolve_merge_proposal_ref(ctx: AppContext, ref: str) -> str:
    ...
```

短 ID、alias、name disambiguation 不要散落在 CLI/REPL。

---

# 5. 用户消息 registry 的使用规则

项目里可能有类似：

```python
_out("ARTICLE_CREATED", ...)
```

或 `_REGISTRY` message catalog。

这个东西有用，但它属于 presentation / renderer，不是业务层。

正确关系：

```text
app command 返回 code
CLI/REPL renderer 根据 code 查 message registry
```

错误用法：

```python
# 不要在 app/core 里这样
_out("ARTICLE_CREATED")
```

正确用法：

```python
# app
return AppResult(code="ARTICLE_CREATED", params={...}, data={...})

# cli
render_result(result)
```

message registry 可以包含：

```text
text
suggestion
see_also
kind
```

但不应该决定业务流程。  
exit code 由 CLI main 或 AppError 决定，不由 message text 决定。

---

# 6. 同步层判断

如果函数里面有：

```text
Transport
server URL
is_online
clock skew
known peers
network errors
best effort
discover articles
on_synced callback
on_peer_error callback
```

它大概率是：

```text
app/sync.py
```

不是 core。

推荐把 callback 改成事件：

```python
@dataclass(frozen=True)
class SyncEvent:
    code: str
    params: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
```

不要这样：

```python
on_peer_done(server, synced)
on_peer_error(e)
on_peer_skip(server, reason)
```

更好：

```python
events.append(AppNotice(
    code="SYNC_PEER_DONE",
    params={"server": server, "count": synced},
    data={"server": server, "count": synced},
))
```

然后 CLI/REPL 决定怎么显示。

---

# 7. 修改代码前必须先回答的问题

每次要改一个函数，先回答：

```text
1. 这段逻辑属于哪一层？
2. 它是否依赖 CLI/REPL/server？
3. 它是否直接 print/_out/sys.exit？
4. 它是否直接碰 storage/transport？
5. CLI 和 REPL 是否都需要同一段逻辑？
6. 如果是，是否应该放 app？
7. 它是领域规则，还是用户用例编排？
8. 是否应该返回 AppResult 或抛 AppError？
```

如果无法回答，不要直接改 CLI handler。

---

# 8. 典型反模式

## 8.1 CLI handler 变成业务层

坏：

```python
def handle_publish(args):
    db = open_db()
    user = get_current_user()
    article_id = resolve_article_id(args.article)
    check_permission(...)
    publish_article(db, article_id, user.id)
    reconcile_score(...)
    print("Published")
```

好：

```python
def handle_publish(args):
    ctx = build_context(args)
    inp = PublishArticleInput(article_ref=args.article)
    result = publish_article_cmd(ctx, inp)
    return render_result(result)
```

---

## 8.2 在 core 里调用 `_out`

坏：

```python
def submit_review(...):
    if invalid:
        _out("INVALID_SCORE")
```

好：

```python
def submit_review(...):
    if invalid:
        raise InvalidScore(...)
```

然后 app 层翻译：

```python
except InvalidScore as e:
    raise ValidationFailed(code="SCORE_OUT_OF_RANGE", ...)
```

---

## 8.3 REPL 复用 CLI helpers

坏：

```python
from peerpedia_core.cli.helpers import resolve_article, get_current_user
```

好：

```python
from peerpedia_core.app.refs import resolve_article_ref
from peerpedia_core.app.commands.article import show_article
```

---

## 8.4 parser import 所有 handlers

坏：

```python
# cli/parser.py
from peerpedia_core.cli import handlers
```

好：

```python
# parser 只设置 command_id
sub.set_defaults(command_id="article.publish")

# dispatch lazy load
handler = load_handler(args.command_id)
```

---

# 9. 三个具体例子

## 9.1 commit message prompt

```python
def _prompt_commit_message(diff: str = "") -> str:
    ...
```

归类：

```text
CLI
```

原因：

```text
TTY
$EDITOR
tempfile
subprocess
用户交互
```

修改建议：

```text
放 cli/editor.py
不要 _out/sys.exit
抛 CliInputError 或返回 str
```

---

## 9.2 parse score part

```python
def _parse_score_part(part: str, valid_keys, valid_abbr) -> tuple[str, int]:
    ...
```

归类：

```text
app/parsers.py + types/scores.py
```

拆法：

```text
app/parsers.py:
  parse "orig=4" 这种 CLI/REPL 输入格式

types/scores.py 或 rules/reviews.py:
  score dimension 是否合法
  abbreviation normalization
  score 是否在 1-5
```

不要放 CLI，因为 REPL/server/scripts 也需要。  
不要直接 `_out()`，应该抛 `ValidationFailed` 或领域异常。

---

## 9.3 sync_all_peers

```python
def sync_all_peers(db, transport, user_id, callbacks...):
    ...
```

归类：

```text
app/sync.py
```

原因：

```text
编排 transport
遍历 peers
处理 network errors
best-effort policy
discover articles
记录 peer result
```

不属于 core。  
建议返回 `AppResult` + notices，或者 yield events。

---

# 10. app 层会不会比 core 厚？

可以。

但要区分：

```text
app 厚 = 用例流程复杂
core 厚 = 领域规则复杂
```

app 可以厚在：

```text
resolve ref
require user
transaction
call core
call reconcile
translate errors
shape result
experimental gate
```

core 应该厚在：

```text
状态转移
review/fork/merge 规则
score/reputation/sedimentation
数据一致性语义
```

原则：

> **app 可以长，但不应该聪明；core 应该聪明，但不应该知道 UI。**

---

# 11. 推荐迁移顺序

不要一次性大改。

## 阶段一：建立 app 基础

新增：

```text
app/context.py
app/result.py
app/errors.py
app/refs.py
app/parsers.py
```

---

## 阶段二：迁移 read-only 命令

先迁移：

```text
account whoami
article list
article show
review list
notifications list
```

目标：

```text
CLI 和 REPL 都调用同一个 app command
```

---

## 阶段三：迁移简单写入

```text
bookmark add/remove
share add/remove
notification read
review rate
```

---

## 阶段四：迁移核心 workflow

```text
article create
article edit
article publish
review submit
fork
merge propose
merge accept
```

---

## 阶段五：迁移 sync/network

```text
bundle export/import
sync pull/push
sync all peers
discover social
```

并标记：

```text
experimental
```

---

# 12. 对 AI 的具体行为要求

当用户要求你“修某个 CLI/REPL 问题”时，不要马上补 CLI。

你必须先输出简短判断：

```text
Layer classification:
- CLI: ...
- app: ...
- core: ...
- storage: ...
Recommended change: ...
```

然后再改代码。

如果发现 CLI 中有：

```text
business rule
storage direct access
transport direct access
sync orchestration
permission/ref resolution
```

优先建议迁到 app。

如果发现 core 中有：

```text
_out
Rich
argparse
sys.exit
HTTP response
REPL state
```

必须建议移出 core。

---

# 13. 最重要的一句话

PeerPedia 现在的问题不是 core 不够多，而是：

> **缺少 app 层，导致 CLI/REPL 被迫承担用例编排。**

所以以后所有修改都要遵守：

```text
CLI/REPL/server = 入口
app = 用例编排
core = 领域动作
storage = 持久化
compute/rules = 纯规则/计算
transport = 网络传输
```

不要再把新逻辑默认塞进 CLI。