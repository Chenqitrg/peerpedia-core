# Layer Audit — local/network separation

## Principle

**Local operations must work offline.** `peerpedia article create` must not
import `httpx`, `starlette`, or any network module.  If the network stack is
broken or uninstalled, local commands must still run.

Today, `cli/handlers/articles.py` does `from peerpedia_core.sync import
discover_articles`, which imports `httpx` transitively.  Every local command
pulls in the full network stack.

## Current structure (problematic)

```
cli/handlers/articles.py
  └→ sync.discovery          ← imports httpx transitively
  └→ cli.sync_utils          ← imports sync/ (network)

cli/handlers/social.py
  └→ transport               ← direct httpx import!

sync/bundle_server.py        ← called ONLY by transport/http_server.py, lives in sync/
sync/social_server.py        ← called ONLY by transport/http_server.py, lives in sync/
sync/discovery.py            ← orchestrates fetch→merge, IS orchestration
commands/discover.py         ← pure DB merge, IS storage CRUD
```

## Proposed structure

```
                         LOCAL (works offline)          NETWORK (needs connectivity)
                         ─────────────────────          ──────────────────────────────
Layer 0: foundations     storage/ (git + db)
                         workflow/ (pure compute)
                         policies/ (permissions)
                         config/, types/, exceptions

Layer 1: orchestration   commands/ (touches git+db)
                         ├─ articles.py                 └─ commands/discovery.py
                         ├─ reviews.py                     (fetch→merge orchestration)
                         ├─ workflow.py                    was sync/discovery.py
                         └─ ...

Layer 2: storage CRUD    └─ storage/db/crud_social.py
                              (merge_users, merge_follows,
                               merge_article_meta)
                              was commands/discover.py

Layer 3: protocol                                       sync/ (pure git bundle protocol)
                                                          ├─ git_bundle.py
                                                          ├─ bundle_client.py
                                                          ├─ pending_queue.py

Layer 4: transport                                       transport/ (HTTP client + server)
                                                          ├─ http_client.py (httpx)
                                                          ├─ http_server.py (ASGI routing)
                                                          │    was server/app.py
                                                          └─ __init__.py (facade re-exports)

Layer 5: CLI              cli/ (local commands)         cli/ (network commands)
                          article create/edit/list       sync push/pull/status
                          follow/unfollow (local DB)     following --server
                          bookmark add/remove            article list --user --server
                          → MUST NOT import sync/        → CAN import sync/
```

## Module moves

| From | To | Why |
|------|----|-----|
| `sync/bundle_server.py` | `server/handlers/bundle.py` | Only called by server routes — no other caller |
| `sync/social_server.py` | `server/handlers/social.py` | Only called by server routes — no other caller |
| `sync/discovery.py` | `commands/discovery.py` | It's orchestration (fetch→merge), belongs in commands/ |
| `commands/discover.py` | `storage/db/crud_social.py` | Pure DB merge — same layer as crud_article.py, crud_user.py |
| `sync/transport/__init__.py` | `transport/__init__.py` | Fetch helper is transport concern, not orchestration |

## Import rules

### Hard constraints

1. **`cli/` local handlers** must NOT import `sync/` or `httpx` at module level.
   Network functions must be lazy-imported inside the function body that uses them.

2. **`commands/`** may import `sync/` only in discovery functions — never in
   article/review CRUD functions.

3. **`server/`** may import everything — it IS the network layer.

4. **`storage/`** must NOT import `sync/`, `commands/`, `server/`, or `cli/`.

5. **`sync/`** must NOT import `server/`, `cli/`, or `storage/` (except
   `sync/bundle_client.py` which imports `commands/apply_sync_bundle` — this is
   allowed as a bridge between protocol and orchestration).

### Lazy import pattern

```python
# cli/handlers/articles.py — local commands work offline
def _cmd_article_list(db, args):
    if args.server:
        from peerpedia_core.commands.discovery import discover_articles  # lazy
        discover_articles(db, server, args.user)
    # ... rest is pure local
```

## What gets simpler

### sync/ shrinks to pure protocol

```
sync/
├── __init__.py            exports: sync_article, is_online, pending_queue
├── git_bundle.py          pure protocol — create_bundle, ingest_bundle, find_common_ancestor
├── monotonic_search.py    k-exponential search algorithm
├── bundle_client.py       client orchestration — sync_article, pull_incremental
├── transport/
│   ├── __init__.py        facade — switch HTTP ↔ P2P here
│   └── http.py            httpx client — fetch_head, push_bundle, fetch_following, etc.
├── network.py             is_online
└── pending_queue.py       offline operation queue
```

### server/ is self-contained

```
server/
├── __init__.py
├── app.py                 ASGI factory + routes + error handlers (already clean)
└── handlers/
    ├── bundle.py          get_head, get_bundle, apply_sync, check_ancestor, create_article
    └── social.py          get_following, get_followers, get_articles, get_bookmarks,
                           handle_follow, handle_unfollow, handle_bookmark
```

### storage/db/ owns all CRUD

```
storage/db/
├── __init__.py            db_session, db_repl_setup
├── engine.py
├── models.py
├── session_utils.py
├── crud_article.py
├── crud_user.py
├── crud_review.py
├── crud_bookmark.py
├── crud_merge.py
├── crud_maintainer.py
└── crud_social.py         merge_users, merge_follows, merge_article_meta  ← was commands/discover.py
```

## What this enables

- `pip install peerpedia-core` → local article creation, editing, compilation work immediately
- `pip install peerpedia-core[server]` → adds starlette, uvicorn for `peerpedia server start`
- `pip install peerpedia-core[p2p]` (future) → adds P2P transport without changing any import
- Architecture tests can verify: "no module outside sync/ imports httpx"
- Tests can run with `--no-network` marker to skip sync tests
