# CLI / REPL Architecture Audit — 2026-06-28

## Summary

`cli/` is not a thin adapter layer. It currently functions as half an application
layer, half an orchestration layer, and half a network/sync layer.  `repl/` sits
on top of `cli/`, amplifying the problem.  This document identifies the
dangerous coupling points and proposes a concrete migration path.

---

## 1. Current Import Graph (problematic edges only)

```
repl
 └─ cli
     ├─ parser
     │   └─ handlers (ALL loaded eagerly)
     │       ├─ helpers
     │       │   ├─ bundle_utils
     │       │   │   ├─ core.sync_batch
     │       │   │   └─ transport
     │       │   ├─ core.sync_article
     │       │   ├─ crypto
     │       │   └─ core (many modules)
     │       ├─ core
     │       ├─ storage (direct imports — forbidden)
     │       │   ├─ storage.peers
     │       │   ├─ storage.db.guards
     │       │   └─ storage.db.crud_user
     │       └─ server (direct import)
     └─ helpers (depends on bundle_utils, creating a cycle)
```

**Consequence:** `import parser` → loads all handlers → loads sync, transport,
storage, crypto, server.  REPL inherits all of this.

---

## 2. Dangerous Coupling Points

### 2.1 `cli.helpers` is too heavy

Imports: `bundle_utils`, `display`, `msgs`, `config.paths`, `core`,
`core.sync_article`, `crypto`, `exceptions`, `types`, `types.scores`.

This single file mixes context construction, user session, ID resolution,
crypto, sync, output rendering, and error handling.  It is the number one
source of coupling in the CLI layer.

**Fix:**
- Split into `app/context.py`, `app/result.py`, `app/errors.py`, `app/refs.py`.
- CLI/REPL import from `app/`, not `cli/helpers.py`.

### 2.2 `cli.bundle_utils` does not belong in CLI

Imports: `cli.helpers`, `config.paths`, `core.sync_batch`, `exceptions`,
`time`, `transport`.

This is sync/batch orchestration, not CLI utility logic.  It is imported by
11 handler files: `bookmark.py`, `bootstrap.py`, `bundle.py`, `create.py`,
`edit.py`, `login.py`, `read.py`, `school.py`, `server.py`, `share.py`,
`social.py`.

**Fix:**
- Move sync/batch logic to `core/sync_batch.py` (already done).
- Move CLI wrappers (`_try_sync`, `_try_sync_all`) to `app/commands/sync.py`.
- Handlers call `app.commands.sync.sync_all()` instead of
  `cli.bundle_utils._try_sync()`.

### 2.3 `cli.parser` eagerly imports all handlers

```
cli/parser.py → cli.handlers → ALL handler files
```

This means importing parser loads every handler, and transitively loads
core, sync, transport, storage, crypto, and server.

**Fix:**
- `cli/parser.py` defines argparse grammar only.  Does not import
  `cli.handlers`.
- Each subcommand sets `command_id` (e.g., `"article.create"`).
- New `cli/dispatch.py` maps `command_id → handler` and lazy-loads on first
  call.

### 2.4 `cli.helpers` ↔ `cli.bundle_utils` circular dependency

```
cli/helpers.py  →  cli/bundle_utils.py  (lazy import for _TRANSPORT)
cli/bundle_utils.py  →  cli/helpers.py  (_out, _get_session_user)
```

**Fix:**
- Move `_out`, `_log`, `_die`, `_show`, `_json_out`, `_ok` → `cli/output.py`.
- Both `helpers.py` and `bundle_utils.py` import from `cli/output.py`.

### 2.5 CLI handlers directly import `storage/`

Violations found:

| File | Imports |
|------|---------|
| `create.py` | `storage.db.guards` |
| `edit.py` | `storage.db.guards` |
| `register.py` | `storage.db.crud_user` |
| `bootstrap.py` | `storage.peers` |
| `login.py` | `storage.peers` |
| `server.py` | `storage.peers` |

**Fix:**
- Move logic to `app/commands/*` which calls `core/`, not `storage/`.
- `server.py` (server start) is the only justified exception.

### 2.6 CLI handlers directly import `core.sync_*`

| File | Imports |
|------|---------|
| `bundle.py` | `core.sync_article`, `core.sync_social` |
| `login.py` | `core.sync_article` |
| `read.py` | `core.sync_social` |
| `social.py` | `core.sync_social` |

**Fix:**
- Move network-aware commands to `app/commands/sync.py`.
- Read-only commands (`read.py`) should not know about network discovery.

### 2.7 REPL depends on `cli.helpers` and `cli.__init__`

```
repl/__init__.py  →  cli, cli.display, cli.helpers, cli.parser
repl/state.py     →  cli, cli.helpers
repl/meta.py      →  cli.helpers
repl/dispatch.py  →  cli.helpers
repl/browse.py    →  cli.display, cli.helpers
```

**Fix:**
- REPL should import from `app/` (context, result, errors, commands).
- REPL may temporarily import `cli.parser` for command grammar, but NOT
  `cli.helpers` or `cli`.

---

## 3. Target Architecture

```
repl  ──→  app.commands  +  app.context  +  app.result
cli   ──→  app.commands  +  app.context  +  app.result
server ─→  app.commands  +  app.context  +  app.result

app/
  context.py     ← workspace, db, user, signing key, transport
  result.py      ← unified return type for CLI/REPL/server
  errors.py      ← AppError → exit code / JSON
  refs.py        ← short ID / alias / user ref / article ref resolution
  commands/
    account.py   ← register, login, whoami, delete
    article.py   ← create, read, update, delete, publish
    review.py    ← submit, reply, invite, rate
    social.py    ← follow, unfollow, share, bookmark, alias
    fork.py      ← fork, merge propose/accept/withdraw
    bundle.py    ← sync push/pull/discover
```

### Layer Rules (enforceable by tests)

| Layer | May import | Must NOT import |
|-------|-----------|-----------------|
| `compute/` | nothing | `cli/`, `repl/`, `server/`, `transport/`, `storage/` |
| `rules/` | nothing | `cli/`, `repl/`, `server/`, `transport/` |
| `core/` | `storage/`, `compute/`, `rules/`, `types/`, `config/` | `cli/`, `repl/`, `server/` |
| `app/` | `core/`, `storage/`, `transport/`, `config/`, `crypto/` | `cli/`, `repl/`, `server/` |
| `cli/` | `app/`, `types/`, `config/` | `storage/`, `transport/`, `server/` (except `server start`) |
| `repl/` | `app/` + `cli.parser` (temporary) | `cli.helpers`, `cli.handlers`, `storage/`, `transport/` |
| `server/` | `app/` | `cli/`, `repl/` |

### Architecture tests to add

```python
def test_repl_does_not_import_cli_helpers():
    for path in Path("peerpedia_core/repl").rglob("*.py"):
        imports = imports_of(path)
        assert "peerpedia_core.cli.helpers" not in imports
        assert "peerpedia_core.cli" not in imports


def test_cli_parser_does_not_import_handlers():
    imports = imports_of(Path("peerpedia_core/cli/parser.py"))
    assert "peerpedia_core.cli.handlers" not in imports


def test_cli_helpers_does_not_import_sync_or_transport():
    imports = imports_of(Path("peerpedia_core/cli/helpers.py"))
    assert "peerpedia_core.core.sync_article" not in imports
    assert "peerpedia_core.transport" not in imports


def test_cli_handlers_do_not_import_storage():
    allowed = {"server.py"}  # server start is the only exception
    for path in Path("peerpedia_core/cli/handlers").rglob("*.py"):
        if path.name in allowed:
            continue
        imports = imports_of(path)
        bad = [x for x in imports if x.startswith("peerpedia_core.storage")]
        assert not bad, f"{path} imports storage: {bad}"
```

---

## 4. Migration Plan (incremental, low-risk)

### Phase 1: Split parser from handlers (high value, low risk)

1. Add `command_id` to every subcommand in `cli/parser.py`.
2. Create `cli/dispatch.py` with a `command_id → handler` map.
3. Change parser to NOT import `cli.handlers`.
4. Handlers are lazy-loaded on first invocation.

**Goal:** `import parser` no longer loads sync, transport, storage, or server.

### Phase 2: Create `app/` foundation types

1. `app/context.py` — `AppContext` dataclass.
2. `app/result.py` — `AppResult` dataclass.
3. `app/errors.py` — `AppError` hierarchy.
4. `app/refs.py` — ID / alias / username resolution.

Migrate 3 read-only commands first:

- `article list` → `app/commands/article.py`
- `article show` → `app/commands/article.py`
- `account whoami` → `app/commands/account.py`

**Goal:** CLI and REPL both call the same `app.commands` entry points.

### Phase 3: Detach REPL from `cli.helpers`

1. `repl/state.py` → import from `app.context` instead of `cli`.
2. `repl/meta.py` → import from `app.result` instead of `cli.helpers`.
3. `repl/dispatch.py` → import from `app.commands` instead of `cli.helpers`.

**Goal:** `repl/` has zero imports from `cli.helpers` and `cli`.

### Phase 4: Extract `cli/output.py` and break the `helpers ↔ bundle_utils` cycle

1. Move `_out`, `_log`, `_die`, `_show`, `_json_out`, `_ok` → `cli/output.py`.
2. `helpers.py` re-exports from `cli/output.py` for backward compat.
3. Remove `helpers.py → bundle_utils.py` import.

### Phase 5: Move `bundle_utils` sync wrappers to `app/commands/bundle.py`

1. Create `app/commands/bundle.py` with `sync_all(ctx)` and `sync_all_peers(ctx)`.
2. `cli/bundle_utils.py` becomes a thin re-export wrapper.
3. Handlers call `app.commands.bundle.sync_all(ctx)`.

### Phase 6: Remove storage imports from CLI handlers

Move each handler's core logic to `app/commands/`:

- `register.py` → `app/commands/account.py`
- `create.py` → `app/commands/article.py`
- `edit.py` → `app/commands/article.py`
- `bootstrap.py` → `app/commands/account.py`
- `login.py` → `app/commands/account.py`

---

## 5. Immediate Actions (this session)

- [ ] Create `cli/output.py` and break `helpers ↔ bundle_utils` cycle
- [ ] Fix `login.py`, `bootstrap.py`, `server.py`, `register.py` to not import `storage/` directly
- [ ] Update `tests/test_architecture.py` with the new layer rules
- [ ] Update `CLAUDE.md` with the new architecture diagram
