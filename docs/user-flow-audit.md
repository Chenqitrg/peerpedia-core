# 用户流与系统逻辑审计报告

**日期:** 2026-06-24
**分支:** main
**审查焦点:** 缺失的用户操作、逻辑不自洽、规则设计漏洞

---

## 总览

审计覆盖 20 个阶段，发现 **35 个逻辑/功能缺口**（含旧系统可借鉴的 10 个 API 端点）：

| 严重程度 | 数量 | 说明 |
|----------|------|------|
| 🔴 MVP 阻塞 — 不修系统不可用 | 7 | 取消关注不传播、密钥轮换无通知、无沉淀池上限、self-review 检查顺序错误、提案方无法关闭、引用系统（仅 DB 无 UI）、无平台审核层 |
| 🟡 MVP 需要但可延后 | 9 | 多设备登录、全员同意发布、maintainer 转让、通知系统、多文件文章、标签系统、编译引用解析、账号删除/改名、fork_count 递减 |
| 🟢 锦上添花 | 18 | 转发、arXiv 镜像、版本标签/diff、作者反驳、评论更新、数据导出/导入、浏览历史、推荐/趋势、举报、互关查询、merge proposal 列表、归档状态、小修改路径、分支控制、评审员校准、孤立 forked_from、全局 O(n) 扫描 |
| 🔵 旧系统 API 待纳入 | 10 | diff、评审讨论串、feed/pool、编译预览/下载、书签路由、评审路由、合并路由、引用路由、用户更新 |

---

## 一、账号生命周期 — 缺少 4 个操作

### 🔴 1. 无法删除/注销账号

没有 `delete_user`，没有 `is_active` 标志，没有软删除。用户的文章、评论、关注关系永久存在。

**影响:** 没有 GDPR 合规路径，没有"离开系统"的方式。

### 🔴 2. 密钥轮换缺少 peer 通知协议

`update_user_public_key` 更新本地公钥，但远程 peer 的 TOFU 检查（`bundle.py:270-277`）比较存储的公钥和提交签名。如果用户轮换密钥并推送新提交，远程 peer 同步时会触发 `SignatureVerificationError`。

**密钥轮换与 TOFU 本身是相容的**——只要密钥所有者在轮换时主动通知所有已知 peer 更新公钥。但当前系统缺少这个通知协议：没有 `push_key_rotation` 端点，没有 gossip 传播，peer 只能通过同步失败被动发现密钥变更。

### 🟡 3. 缺少社交密钥恢复

当本地密钥丢失（非轮换，而是存储介质损坏/丢失），需要通过**多个信任朋友的社交证明**来重新建立身份。当前系统完全没有这个机制：没有恢复见证人、没有阈值签名、没有社交恢复协议。现有的 `account recover` 只能从 salt + password 重新派生密钥——如果 salt 也丢失，密钥就永久丢失了。

### 🟡 4. 无法更改 display name

`User.name` 创建后不可修改。没有 `update_user_name` 函数。同时 `User.name` 没有 unique 约束，导致 `get_user_by_name` 返回列表，查找歧义。

---

## 二、文章生命周期 — 5 个状态机问题

### 🟡 5. 缺少平台审核/管理员删除能力

```
DRAFT → SEDIMENTATION → PUBLISHED → [Forever]
```

**用户删除已发布文章是设计上的有意限制**——影响力一旦发布不可撤回。但系统缺少平台级的管理员/审核层来执行不良内容（色情、违法、侵权）的删除。当前没有：
- 管理员角色或权限模型
- 平台级文章删除/隐藏/标记能力
- 内容审核工作流（标记 → 审核 → 删除/驳回）
- 用户举报机制

`assert_can_delete_article` 仅允许 `draft` 状态的维护者删除——没有任何代码路径允许第三方（管理员）删除任何状态的文章。

### ✅ 6. 沉淀期无法撤回（设计正确）

```
SEDIMENTATION → PUBLISHED (auto, after N days)
SEDIMENTATION → DRAFT ([INTENTIONALLY MISSING])
```

沉淀期不可撤回是有意设计。两个目的：
1. **鼓励犯错**——进入沉淀期的文章必须完成周期，作者从错误中学习而非 panic-revert
2. **增加随意发布的成本**——不能发完后悔就撤回，发布前必须慎重

之前的审计将此项标记为漏洞，现已确认是设计决策。

### 🔴 7. 缺少沉淀池文章上限（反垃圾机制）

**当前没有任何限制作者同时在沉淀池中的文章数量。** 一个用户可以在沉淀池中积压无限数量的文章。这意味着恶意用户可以：
- 批量创建垃圾文章推入沉淀池
- 消耗 peer 的存储和同步资源
- 稀释社区评审注意力

应该有一个上限（如 3-5 篇），且应作为 `publish_article` 的前置检查：`count_articles_by_author_in_sedimentation(author_id) >= MAX_SEDIMENTATION_PER_AUTHOR`。如果超限，应要求等待现有沉淀文章发布后才能提交新文章。

### 🟡 8. fork_count 永不递减

`fork` 创建时 `increment_fork_count`，但 `delete_article` 不递减。多次 fork/delete 后，`fork_count` 反映的是"历史上被 fork 过的总次数"而非"当前活跃的 fork 数"。

### 🟢 9. 发布后编辑无"小修改"路径

修改发布文章中一个字符也需要 3 天沉淀期。没有 typo fix 快捷路径。

---

## 三、社交图谱 — 5 个缺口

### 🔴 10. 取消关注不会传播到远程 peer

`merge_follows`（`discover.py:72-101`）仅**添加**关注行。取消关注仅在本地生效。如果用户 A 在服务器 X 上取消关注 B，服务器 Y 上的 peer 永远不知道，仍然认为 A 关注 B。

**这是一个协议级设计漏洞：** 社交图谱同步是只增不减的。

### 🟡 11. 无法阻止用户

**拒绝被关注是有意设计——关注权属于关注者，不属于被关注者。** 这避免了学术圈中 senior 学者可以阻止 junior 学者关注他们、从而隐藏自己动态的情况。

但 current 系统也没有 block 能力——阻止特定用户查看/交互你的内容（评论、@提及等）。Block 和"拒绝被关注"是不同概念：前者是内容可见性控制，后者是社交图谱控制。Block 的缺失是否是有意设计尚待确认。

### 🟡 12. 无法发现新的 peer/用户

没有全局发现机制（无 DHT、无引导节点、无用户目录端点）。你需要先知道一个 peer URL 才能发现其用户。代码注释显式承认：

```
TODO(social-graph): sync discover — traverse the social graph to
find new peers and articles.
```

### 🟢 13. 无互相关注查询

`get_following` + `get_followers` 存在，但没有 `get_mutual_follows`。调用者需要手动计算交集。

### 🟢 14. `follow` 和 `following` 命令层级不一致

`follow`/`unfollow` 是顶层命令，但 `following`/`followers` 是单独的命令组（使用空字符串作为子命令名）。语义相关的操作被分散在不同层级。

---

## 四、合并提案 — 1 个真实缺口（其余为有意设计）

### 设计哲学

合并提案的机制有明确的社会意图：**目标维护者不能拒绝提案，只能由提案发起方关闭。** 这让原文章作者面临社会压力——不能一键驳回他人的贡献——从而促进学术合作，防止学阀把持话语权。

提案被关闭后应**归档而非删除**，保留完整的协作历史。

基于这个设计哲学重新评估：

### 🟡 15. 提案发起方无法关闭提案（真实缺口）

`withdraw_merge_proposal` 在 CRUD 和命令层均不存在。按照设计意图，提案方应该可以关闭自己的提案，但当前代码完全没有这个路径。提案发起方一旦创建提案，既不能撤回也不能关闭——和目标的维护者一样被锁死。

### ✅ 16. `reject_merge_proposal` 未接线（设计正确）

`crud_merge.py:61-62` 的 `reject_merge_proposal` 不应被接线。目标维护者不能拒绝提案是有意设计。该 CRUD 函数建议标记为废弃或重新用途为"提案方关闭"。

### 🟡 17. 同一 fork 可以提案到多个目标（仍然是个问题）

`create_merge_proposal` 不检查是否已有开放提案。如果 fork 被目标 A 接受，目标 B 上的提案仍然开放，指向已经改变的历史。社会机制无法解决这个技术一致性问题。

### 🟡 18. 缺少归档状态（设计缺口）

当前 MergeProposal 有三个状态：`open`、`accepted`、`rejected`。按照设计意图，应该有第四个状态 `closed`（由提案方关闭）或 `withdrawn`，且对应的提案行应该被归档而非删除。目前没有归档机制。

---

---

## 五、引用系统 — 仅 Model/CRUD 层存在，上层全部缺失

引用系统是最典型的"底层完备、上层空白"案例。`Citation` 模型和 5 个 CRUD 函数已经实现并 100% 测试覆盖（`test_crud.py`），但从用户角度看**引用功能完全不存在**：

| 层 | 状态 |
|---|------|
| `models.py` — Citation 表（from/to/p(forward)/p(backward)） | ✅ 存在 |
| `crud_citation.py` — 5 个 CRUD 函数 | ✅ 存在，100% 测试覆盖 |
| `commands/` — 命令层接入 | ❌ 不存在 |
| CLI — 用户可操作的引用命令 | ❌ 不存在 |
| 编译时引用解析（`[@key]` → 渲染引用） | ❌ 不存在 |
| 引用图谱可视化/遍历 | ❌ 不存在 |
| 引用跳转（文章 A 的引用列表 → 点击跳转到文章 B） | ❌ 不存在 |

### 缺失的用户操作
- 用户在文章正文中写 `[@smith2024]` 但编译器不理它
- 没有 `peerpedia citation add <from> <to>` 命令
- 没有 `peerpedia article show` 时列出"被引/引用"链
- 引用只存在于 DB 中，从不出现在用户界面

---

## 六、编译与内容格式 — 3 个缺口

### 🟡 无引用编译解析

编译器不处理 `[@key]` 引用标记。Markdown 正文中的引用原样输出，不生成参考文献列表。

### 🟡 无 arXiv 元数据镜像

没有从 arXiv API 拉取文章元数据（标题、作者、摘要）的功能。新用户创建文章时需要手动输入所有信息，即使该文章已在 arXiv 上存在。

### 🟡 不支持多文件文章

当前只认仓库根目录下的 `article.md` 或 `article.typ`。如果一个文章需要：
- 多个 Markdown 文件（章节拆分）
- 图片/图表文件
- 数据文件
- 补充材料

当前系统不支持。`_find_article_file` 硬编码查找单个文件。

---

## 七、转发文章（Repost）— 完全缺失

转发是学术传播的核心机制：看到一个好文章 → 转发到自己的 feed 增加曝光。当前没有 `repost_article` 功能，也没有转发计数。与 fork（创建可编辑副本）不同，repost 是轻量级的分享操作。

---

## 八、Git 分支控制 — 完全缺失

当前没有任何机制阻止用户在文章仓库中创建分支：

- `git_backend.py` 不检查也不限制分支创建
- `init_article_repo` 创建一个 `main` 分支但不对其他分支做限制
- Bundle 协议传输分支信息时可以传入任意分支

如果一个用户创建了多个分支并推送，peer 同步时行为不可预测。系统设计上文章 repo 应该是单分支的（所有操作都在 `main` 分支），但没有技术执行这一约束。

---

---

## 九、多设备与会话 — 1 个缺口

### 🟡 多设备登录不支持

当前 session 是本地文件（`~/.peerpedia/session.json`），包含私钥。代码中已标记 `TODO(multi-device)`：用户在一台设备上注册后，另一台设备上无法登录——即使知道密码。`account recover` 可以从 password + salt 重新派生密钥，所以理论上是可行的，但需要用户主动执行 recover 而非 login。正常流程应在任意设备上 `account login --name X` → 输入密码 → 自动派生密钥。

---

## 十、协作与共同维护 — 2 个缺口

### 🟡 缺少全员同意发布模型

`policies/articles.py:198` 标记了 `TODO: unanimous consent`。当前单个 maintainer 可以独立发布文章。但对于多作者文章，应该要求**所有 maintainer 一致同意**才能进入沉淀期。这是学术出版的惯例——所有作者必须同意投稿。

### 🟡 maintainer 无法转让/退出

当前只能 `add` 和 `remove` maintainer（需要已有 maintainer 执行）。但如果一个文章的**唯一 maintainer 离开/消失**，文章变成无人维护状态——无法编辑、无法发布、无法添加新的 maintainer。需要：
- maintainer 主动退出机制（把自己从列表中移除）
- 或者系统管理员/社区接管机制

---

## 十一、通知系统 — 1 个缺口（整个子系统缺失）

`commands/merge.py:6` 标记了 `TODO(merge-notify)`。没有任何通知机制：
- 有人评论了你的文章 → 不知道
- 有人对你关注的作者的文章提交了评审 → 不知道
- 有人向你提出了合并提案 → 不知道（当前提案方必须手动告诉维护者执行 `merge accept`）
- 你关注的用户发布了新文章 → 不知道
- 你的文章通过了沉淀期 → 不知道

一个去中心化的 P2P 通知系统确实复杂，但至少本地应有通知中心（如 `peerpedia notifications` 显示未读事件）。

---

## 十二、文章版本与标签 — 2 个缺口

### 🟢 无法给版本打标签

文章仓库是 Git repo，理论上可以用 `git tag`。但系统没有暴露版本标签功能：无法标记 `v1.0`、`preprint`、`camera-ready`。编译器/同步也不识别标签。

### 🟢 无法 diff 两个版本

虽然底层 Git 支持，但 CLI 没有 `article diff <id> --from <commit> --to <commit>` 命令来查看版本间的变动。

---

## 十三、评审流程 — 2 个缺口

### 🟡 无作者反驳/回应

评审系统只有单向的 score + comment。作者无法：
- 回应评审意见（author rebuttal）
- 修改文章后标注"已根据评审 #X 修改"
- 标记某个评审为"已处理"

这在学术评审中是标准流程。

### 🟡 评审无讨论串（旧系统有）

旧版 Review 模型有 `thread` 字段，API 有 `POST .../reviews/{id}/messages` 端点。评审者与作者可以在评审下进行对话（澄清问题、回应批评）。当前 peerpedia-core 的 Review 模型已移除此字段，评审是单向的。

### 🔴 作者无法回复评审

与上条相关但更基础：作者对评审的回复应该写入评审者目录下的 git repo（和评审本身放在一起），形成完整的对话记录。当前只有评审者提交 score + comment，作者完全没有回复路径。这是评审闭环的关键缺失——评审不应该是单方面判决，而是对话。

### 🟢 评审提交后无法更新

评审一旦提交就是不可变的。评审者发现错误后无法修正评分或补充评论。

---

## 十四、数据导出与迁移 — 2 个缺口

### 🟡 无数据导出

用户无法导出：
- 自己的文章（BibTeX/LaTeX/PDF）
- 自己的 profile 和密钥
- 完整数据包（迁移到另一台机器）

编译器可以从 Markdown → PDF/HTML，但没有 BibTeX 或 LaTeX 源码导出。

### 🟢 无数据导入

无法从 arXiv API、BibTeX 文件批量导入引用，也无法从 Overleaf 导入草稿。

---

## 十五、标签系统 — Wiki 风格标签图谱完全缺失

当前 `Article.keywords` 是 `JSONList`——一个扁平的字符串列表，没有结构：

```python
keywords = Column(JSONList, nullable=True)  # 例如 ["机器学习", "自然语言处理"]
```

**Wiki 风格的标签系统**将标签提升为一级实体，标签之间可互相关联形成知识图谱：
- "自然语言处理" **is_subfield_of** "机器学习"
- "机器学习" **is_subfield_of** "计算机科学"
- "计算机科学" **related_to** "数学"
- "BERT" **is_implementation_of** "Transformer"

缺失的系统组件：

| 组件 | 当前状态 | Wiki 模式 |
|------|----------|-----------|
| Tag 实体表 | 不存在 | `Tag(name, description, wiki)` |
| Tag-Tag 关系 | 不存在 | `TagRelation(from, to, type: subfield_of/related_to/see_also)` |
| Article-Tag 关系 | `JSONList` blob | `ArticleTag(article_id, tag_id)` — normalized |
| 标签浏览 | 不存在 | 按标签浏览文章，标签云 |
| 标签图谱 | 不存在 | 标签关联网络可视化 |

### 🟡 无浏览历史

`parser.py:242` 标记了 `TODO(ux-history)`。用户阅读某篇文章后，该行为没有被记录。无法查看"我最近读过的文章"。

### 🟡 无文章推荐/趋势

没有 trending/popular 算法、没有"你可能感兴趣的文章"、没有基于引用图谱/标签图谱的推荐。文章发现完全依赖手动搜索和已知关注关系。

---

## 十七、评论/举报/审核 — 1 个缺口

### 🟡 无用户举报机制

没有 `report_article` 功能。用户无法标记不良内容（抄袭、骚扰、错误信息）。审核缺失无法形成闭环——管理员没有输入信号来触发删除操作。

---

## 十八、评审与评分 — 2 个设计问题

### 🟡 19. `publish_article` 中 self-review 检查在状态变更之后

`publish.py` 先写入评审（git+DB）、改变状态为 sedimentation、设置 sink_start、计算分数，**然后**才检查 `require_self_review_for_publish`。如果这个检查失败（虽然理论上不应该，因为评审刚被写入），文章已经处于 sedimentation 状态。

### 🟢 20. 无评审员声誉校准

声誉系统计算评审员权重（`get_reviewer_weight`），但没有针对评分偏差的校准。一个总是给 5/5 的评审员和一个严格的评审员在加权前被视为相同。

### ~~20. 去匿名化风险~~（已撤回）

~~之前担心同一个评审员的匿名 ID 在不同文章间可关联。~~ 实际实现中 `_derive_anonymous_id` 的种子包含 `article_id`，同一评审员在不同文章上产生完全不同的 hash，无法跨文章关联。匿名性保护是正确实现的。

---

## 十九、同步与数据完整性 — 2 个协议漏洞

### 🟡 21. 拉取后的全局扫描是 O(n) 浪费

`apply_sync_bundle`（`bundle.py:224`）在每次同步后无条件调用 `publish_ready_articles(db)`，扫描整个文章表。对于频繁的小同步，这是 O(n) 的浪费。应该只检查本次同步涉及的文章。

### 🟢 22. 孤立的 forked_from 引用

`Article.forked_from` 是一个普通 `String` 字段，不是 `ForeignKey`。如果原文章被删除，fork 的 `forked_from` 指向不存在的文章 ID。查询"这个文章有哪些 fork"将返回空结果，但 fork 记录本身仍然存在。

---

---

## 二十、从旧系统可借鉴的 API 端点

旧版 peerpedia（已归档）的前端做了太多后端该做的事（sync 冲突处理、commit flow、草稿持久化都在客户端）。重构后这些逻辑应收归 core，暴露为 HTTP 端点。以下是旧版 API 中值得纳入 transport/routes/ 的端点：

### 🔴 应纳入（后端逻辑，前端不该自己做）

| 旧端点 | 对应 core 能力 | 说明 |
|--------|---------------|------|
| `GET /articles/{id}/diff/{h1}/{h2}` | `git_backend.py` 已有 diff | 文章版本差异对比，前端不应自己跑 git diff |
| `POST /articles/{id}/reviews/{id}/messages` | 评审讨论串 + 作者回复 | 评审者与作者的对话，旧版 Review 模型有 `thread` 字段，新版缺失 |
| `POST /compile-preview` + `POST /compile-download` | `compiler.py` 已有 | 编译预览/下载，核心能力已有只需 HTTP 包装 |

### 🟡 core 已有逻辑，只需 HTTP 路由

| 旧端点 | 对应 core 能力 | 说明 |
|--------|---------------|------|
| `GET /feed` + `GET /feed/cache` | `commands/views.py` → `get_following_views()` | **已存在**，只需加路由 |
| `GET /pool` | `crud_article.list_articles(status="sedimentation")` | **已存在**，只需加路由 |

### 🟡 应纳入（CRUD 层已有，缺 HTTP 路由）

| 旧端点 | 对应 core 能力 | 说明 |
|--------|---------------|------|
| `GET/DELETE /bookmarks` | `crud_bookmark.py` 已有 | 书签管理，CRUD 完备，缺路由 |
| `GET/POST /articles/{id}/reviews` | `commands/reviews.py` 已有 | 评审提交/查看，命令层已有，缺路由 |
| `GET/POST /articles/{id}/merge-proposals` | `crud_merge.py` 已有 | 合并提案 CRUD，缺路由 |
| `GET /articles/{id}/citations` | `crud_citation.py` 已有 | 引用查看，CRUD 完备，缺路由 |
| `PUT /users/{id}` | 缺失 | 更新用户 profile，旧版有，新版无 |

### 🟢 参考设计但不急

| 资产 | 说明 |
|------|------|
| `docs/authority-matrix.md` | 每状态×每操作的完整权限矩阵 |
| `design-system/MASTER.md` | GitHub 暗色色板 + EB Garamond/Inter 排版 |
| `frontend/src/api/types.ts` | 30+ TypeScript 接口定义，加 HTTP API 时的 schema 参考 |
| 12 条 ADR | 每条重大架构决策的"为什么"，与 core 方向一致 |

---

## 缺失的 CRUD 操作汇总

以下 CRUD 函数已实现但**有意不接线**（设计决策）：

| CRUD 函数 | 文件 | 不接线的原因 |
|-----------|------|-------------|
| `reject_merge_proposal` | `crud_merge.py:61` | 目标维护者不能拒绝提案——社会压力促进合作 |

以下 CRUD 函数已实现但**未在命令层公开**（可能遗漏）：

| CRUD 函数 | 文件 | 做什么 |
|-----------|------|--------|
| `list_users` | `crud_user.py:121` | 列出所有用户 |
| `get_merge_proposals_for_article` | `crud_merge.py:36` | 查看文章的合并提案列表 |

以下操作**完全缺失**（CRUD 层也不存在）：

| 操作 | 影响 |
|------|------|
| `delete_user` / `deactivate_user` | 无法离开系统 |
| `update_user_name` | 无法改名 |
| `withdraw_merge_proposal` | 提案方无法关闭自己的提案 |
| `block_user` / `unblock_user` | 无法阻止骚扰 |
| `get_mutual_follows` | 无法查看互关 |
| `unpublish_article` | 无法撤回已发布文章（设计上有意限制用户，但平台审核层需要） |
| `archive_article` | 无法软删除/归档 |
| `article delete --force` | 无法在脚本中删除 |

---

## 最危险的 3 个逻辑不自洽

1. **密钥轮换缺少 peer 通知协议**: 轮换密钥后，远程 peer 的 TOFU 检查会拒绝新提交。密钥轮换与 TOFU 本身相容——但需要在轮换时主动通知所有已知 peer 更新公钥。当前这个通知协议不存在。

2. **取消关注不传播**: 本地图和远程图永久分歧。用户以为已经取消关注，但网络上的其他人仍然看到关注关系。这是协议级别的设计错误——社交图谱同步是只增不减的。

3. **无沉淀池上限**: 没有任何机制限制作者同时在沉淀池中的文章数量。恶意用户可以批量灌入垃圾文章，消耗整个网络的存储和评审资源。需要一个硬上限（如 3-5 篇），在 `publish_article` 前置检查。

---

## 推荐修复顺序

### 批处理 1：修复正确性错误
1. 密钥轮换与同步的兼容性（TOFU 模型需要版本化或迁移路径）
2. 取消关注的传播（`merge_follows` 需要支持删除或墓碑）

### 批处理 2：补齐关键用户操作
3. 实现 `delete_user`（或 `deactivate_user`）—— 法律合规
4. 为 `reject_merge_proposal` 添加命令层入口和 CLI 命令
5. 为 `withdraw_merge_proposal` 实现完整路径
6. 实现文章删除/归档/撤回（至少一个退出路径）

### 批处理 3：修复数据完整性
7. fork_count 递减
8. `forked_from` 改为 ForeignKey 或清理孤立引用
9. `merge_follows` 添加 `source` 字段以区分来源

---

## GSTACK REVIEW REPORT

| Runs | Status | Findings |
|------|--------|----------|
| 1 | **DONE_WITH_CONCERNS** | 35 个缺口涵盖 19 个阶段，其中 7 个 MVP 阻塞项 |

### 按优先级分布

| 级别 | 数量 | 代表项 |
|------|------|--------|
| 🔴 MVP 阻塞 | 7 | 取消关注不传播、密钥轮换无通知、无沉淀池上限、self-review 顺序错误、提案方无法关闭、引用仅 DB 无 UI、无平台审核层 |
| 🟡 MVP 可延后 | 9 | 多设备登录、全员同意发布、maintainer 转让、通知、多文件文章、标签系统、编译引用解析、账号改名、fork_count |
| 🟢 锦上添花 | 19 | 转发、arXiv 镜像、版本 tag/diff、作者反驳、数据导出、浏览历史、推荐... |

### 设计确认（5 项经讨论确认的有意设计）

| 机制 | 设计意图 |
|------|----------|
| 用户不能删除已发布文章 | 影响力不可撤回 |
| 沉淀期不可撤回 | 鼓励犯错学习 + 增加随意发布成本 |
| 目标维护者不能 reject merge | 社会压力促进合作，防止学阀 |
| 不能拒绝被关注 | 关注权属于关注者 |
| 文章不可 unpublish | 与不可删除配套 |

### VERDICT

**7 个 MVP 阻塞项中，2 个是协议级 bug（取消关注不传播、密钥轮换无通知），2 个是防护缺失（沉淀池上限、平台审核层），3 个是功能断层（提案方无法关闭、引用仅 DB 无 UI、self-review 检查顺序错误）。** 修复这 7 项后核心用户流可以走通。其余 28 项是锦上添花——真实的学术出版平台需要它们，但不是第一版必须的。

NO UNRESOLVED DECISIONS
