# Code Aesthetics — Design Philosophy

## Architecture

**Layers are directional, each depends only downward:**

```
server/                    Application (HTTP routes, middleware)
cli/ repl/                  User entry points
  ↓
core/                       Domain orchestration (coordinates transport + storage + compute)
  ↓       ↓
transport/  storage/        Infrastructure (swappable, zero upward deps)
               ↓
         compute/ rules/ types/ crypto/   Pure logic (zero IO)
```

**Names must carry information.** Every word must answer "why this, not another":

```
Before                    After                     Why
commands/                 core/                     Domain orchestration, not "CLI commands"
workflow/                 compute/                  Pure algorithms, not "process flows"
policies/                 rules/                    Authorization rules, not "policy documents"
commands/discover.py      storage/db/ingest.py      Pure DB operations, sinks to storage
core/trailers.py          storage/git/trailers.py   Git filesystem operations
social/exchange.py        core/discover.py          Orchestration glue, not "social exchange"
bundle/monotonic.py       compute/monotonic.py      Pure algorithm, belongs in compute
```

**A function belongs to a natural set — find its siblings:**

```
crypto.py:
  pubkey_hex_to_ssh_line         hex → SSH line
  write_key_to_tempfile          private key → temp file
  write_allowed_signers_file     email + pubkey → allowed_signers file
  ↑ SSH signing triad — three functions, one domain

compute/
  bfs.py         graph traversal     } 纯算法
  monotonic.py   binary search       } 零 IO
  reputation.py  scoring             }
```

**One entity, three projections.** Don't force one type to serve all callers:

```
ArticleMetaExchange   — P2P transfer (minimal fields)
ArticleMetaStorage    — DB persistence (ORM projection)
ArticleSnapshot       — Algorithm input (immutable)
```

Naming convention:
- `*Storage` / `*MetaStorage` — ORM model. `Meta` when SOT is in git (article content, review files).
- `*Exchange` — P2P payload. `Meta` only for Article (content ≠ metadata).
- `*Snapshot` — frozen dataclass, algorithm input.

**Package structure reflects domain, not technology:**

```
core/articles/    create update publish sink fork rollback delete diff
core/reviews/     submit invite thread
core/reconcile/   mirror score
```

Each file = one lifecycle transition, ~50-80 lines.

## Style

**Pure core, imperative shell.** `compute/` + `rules/` are pure functions (Set-morphisms). `core/` + `storage/` live in the Kleisli category `Kl(Session →)` — they do IO but compose cleanly.

**Git-first, DB-second.** All mutations: write git commit first, then update DB cache. DB is a projection of git.

**Guard architecture — three layers, each with its own dependencies:**

```
rules/                  Pure logic: takes data, returns or raises. Zero IO.
storage/db/guards       DB-aware: needs Session.
storage/git/guards      Git-aware: needs Repo.
core/guards             Composite: coordinates db + git + rules.
```

**Thin orchestration.** Top-level functions ≤ 20 lines. Each helper does exactly one thing. Phase labels show the flow:

```python
def _process_sink_article(db, article):
    # ── Sink timer check ──
    if article.sink_start is None: return None
    ...
    # ── Count approvals ──
    approval_count = _count_approving_reviews(db, article.id, authors)
    # ── Decide disposition ──
    decision = _decide_sink_disposition(article, approval_count)
    # ── Git: write status marker ──
    if decision != "extended" and has_repo:
        commit_status_marker(rp, decision)
    # ── DB: update status + score ──
    update_article_status(db, article.id, decision)
```

**No bare types.** Never `dict`, always `dict[str, float]`. Never `list`, always `list[UserStorage]`. Never `Any` except at serialization boundaries (`to_dict()`). Never `str | set[str]` on parameters — pick one type, convert at the facade.

**No `Callable[..., X]`.** Always specify the full signature of the callback.

**No union parameters.** `str | set[str] | None` on a parameter means the function doesn't know what it accepts. Pick one type (`set[str]`) and let the facade convert `str` → `{str}`.

**Orchestrators collect, workers do.** `_collect_*` functions delegate to individual checkers. They don't do the work inline.

**Translations live on the type.** `from_exchange` / `to_exchange` live on the Storage model, not scattered across callers:

```python
class UserStorage(Base):
    @classmethod
    def from_exchange(cls, e: UserExchange) -> dict[str, object]:
        return {"id": e.id, "name": e.name, "address": e.address}

    def to_exchange(self) -> UserExchange:
        return UserExchange(id=self.id, name=self.name, address=self.address or "")
```

**JSON converts at the boundary.** `from_json` classmethods on Exchange types:

```python
class UserExchange:
    @classmethod
    def from_json(cls, d: dict) -> UserExchange:
        return cls(id=d["id"], name=d.get("name", d["id"]), address=d.get("address", ""))
```

**No private-underscore imports across packages.** If module `_internal.py` is needed by another package, its content belongs on the public facade.

**Guards check + raise. Actions transform. Never mix them.** `_normalize_score_keys` is not a guard — it mutates, doesn't check. Moved from `guards.py` to `types/scores.py`.

**Reconcile pattern:** extract snapshot from DB → compute pure → write back. The compute step is testable with no DB.

**`require_*` fails fast.** Returns the resource or raises. Callers never check for None.
