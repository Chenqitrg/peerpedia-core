# PeerPedia Test Plan — blind spot audit & invariant coverage

> Target: find bugs in tests' blind spots, not re-test what's already covered.
> Principles: every finding must have a minimal regression test. No style opinions.

## Current baseline

- 949 tests passing (architecture + journey + unit)
- Architecture boundaries locked (`cli/` ∥ `repl/`, `presentation/` pure, etc.)
- CommandSpec is single source of truth for CLI + REPL
- REPL uses per-command DB sessions

## Test coverage by layer

> Coverage measured by: does any test file import this module?
> "0%" = no test directly imports this module. It may still be exercised indirectly
> through higher-level journey tests, but edge cases and error paths are likely untested.

| Layer | Files | Covered | % | Lines | Functions | Risk |
|-------|-------|---------|-----|-------|-----------|------|
| `app/` | 17 | 12 | 71% | 2,247 | 156 | MEDIUM — core logic covered, `commandspec/` not |
| `cli/` | 20 | 13 | 65% | 2,079 | 117 | MEDIUM — `cmds/` tested, infrastructure not |
| **`repl/`** | **11** | **0** | **0%** | **1,645** | **75** | **CRITICAL** |
| **`presentation/`** | **1** | **0** | **0%** | **112** | **6** | LOW |
| **`core/`** | **28** | **8** | **29%** | **2,892** | **129** | **CRITICAL** |
| `storage/` | 30 | 17 | 57% | 4,120 | 234 | MEDIUM — CRUD tested, git/ingest not |
| **`transport/`** | **7** | **1** | **14%** | **874** | **50** | **CRITICAL** |
| **`server/`** | **9** | **1** | **11%** | **862** | **35** | **CRITICAL** |
| `config/` | 3 | 2 | 67% | 400 | 11 | LOW |
| `types/` | 3 | 2 | 67% | 311 | 19 | LOW |
| `root/` | 8 | 5 | 62% | 1,299 | 44 | LOW |

### Modules with ZERO direct test coverage

#### `repl/` — 11 files, 75 functions, 0% coverage

No test file imports any `repl/` module directly. The REPL may be exercised through
`test_repl_journey.py` (end-to-end) or manual testing, but unit-level edge cases
for the parser, session management, display, and dispatch are untested.

| File | Lines | Funcs | Key untested functions |
|------|-------|-------|----------------------|
| `repl/engine.py` | 216 | 5 | `_parse_args`, `_parse_flag`, `_coerce`, `execute`, `_iter_all_specs` |
| `repl/browse.py` | 258 | 25 | `_browse_articles`, `_browse_school`, `_browse_reviews`, `_build_browser` |
| `repl/help.py` | 245 | 7 | `_meta_help`, `_show_topic_help`, `_render_help_text` |
| `repl/state.py` | 184 | 5 | `new_session`, `session_scope`, `close_db`, `_prompt_text`, `_refresh_completions` |
| `repl/display.py` | 140 | 9 | `render_result`, `render_error`, `_render_notice` |
| `repl/meta.py` | 139 | 4 | `_meta_user`, `_meta_article`, `_meta_theme`, `_show_inbox` |
| `repl/dispatch.py` | 134 | 11 | `_dispatch_meta`, all `_handle_*` functions |
| `repl/main.py` | 134 | 3 | `run` |
| `repl/completer.py` | 74 | 4 | `build_flags`, `build_command_list`, `make_completer` |
| `repl/wizards.py` | 67 | 1 | `_meta_write` |
| `repl/banner.py` | 54 | 1 | `show_startup_banner` |

**Highest risk in repl/:** `engine.py:_parse_args` — hand-written arg parser with type coercion
and choices validation. A bug here affects every REPL command.

#### `app/commandspec/` — 3 files, 64 functions, 0% coverage

The shared command specification layer has zero direct tests. CLI and REPL both
consume these definitions at runtime, so errors manifest as runtime bugs.

| File | Lines | Funcs | Risk |
|------|-------|-------|------|
| `app/commandspec/handlers.py` | 231 | 49 | HIGH — every handler maps args dict → typed kwargs. A key name typo = runtime crash |
| `app/commandspec/registry.py` | 306 | 3 | MEDIUM — `find_spec` used by engine; lookup collisions = wrong command dispatched |
| `app/commandspec/schema.py` | 140 | 12 | MEDIUM — schema generation untested; AI tool discovery broken silently |

#### `core/` — 20 uncovered files, 101 functions

Business logic with zero direct test coverage. Journey tests may hit happy paths
but miss guards, error paths, edge cases.

| File | Lines | Funcs | Risk |
|------|-------|-------|------|
| `core/articles/create.py` | 84 | 2 | HIGH — article creation entry point |
| `core/articles/publish.py` | 98 | 2 | HIGH — publish + notifications |
| `core/articles/delete.py` | 41 | 1 | HIGH — soft delete logic |
| `core/articles/rollback.py` | 72 | 1 | MEDIUM |
| `core/articles/sink.py` | 119 | 4 | HIGH — auto-publish sink logic |
| `core/articles/update.py` | 107 | 2 | HIGH — content update + git commit |
| `core/articles/fork.py` | 60 | 1 | MEDIUM |
| `core/articles/diff.py` | 65 | 5 | LOW |
| `core/guards.py` | 119 | 5 | HIGH — signature verification, commit guards |
| `core/reviews/submit.py` | 100 | 3 | HIGH — review submission |
| `core/reviews/thread.py` | 159 | 5 | HIGH — review replies |
| `core/reconcile/mirror.py` | 123 | 5 | MEDIUM — DB↔git reconciliation |
| `core/reconcile/score.py` | 94 | 4 | MEDIUM |
| `core/sync_article.py` | 175 | 9 | HIGH — sync protocol, merge base, bundle |
| `core/sync_social.py` | 154 | 9 | HIGH — social graph sync |
| `core/merge.py` | 143 | 4 | MEDIUM — merge proposals |
| `core/maintainers.py` | 111 | 5 | MEDIUM |
| `core/notifications.py` | 127 | 7 | MEDIUM |

#### `transport/` — 6 uncovered files, 49 functions

HTTP client layer has almost no test coverage.

| File | Lines | Funcs | Risk |
|------|-------|-------|------|
| `transport/http/_core.py` | 137 | 11 | HIGH — HTTP client core (post, get, auth header) |
| `transport/http/articles.py` | 145 | 10 | HIGH — article sync HTTP calls |
| `transport/http/social.py` | 203 | 13 | HIGH — social graph HTTP calls |
| `transport/http/health.py` | 185 | 11 | MEDIUM — health check + clock skew |
| `transport/auth.py` | 69 | 2 | HIGH — Ed25519 auth header signing |
| `transport/guards.py` | 79 | 2 | HIGH — auth header verification |

#### `server/` — 8 uncovered files, 33 functions

| File | Lines | Funcs | Risk |
|------|-------|-------|------|
| `server/routes/articles.py` | 168 | 10 | HIGH — article API endpoints |
| `server/routes/users.py` | 188 | 10 | HIGH — user/social API endpoints |
| `server/middleware/auth.py` | 93 | 2 | HIGH — auth verification middleware |
| `server/routes/peers.py` | 37 | 2 | MEDIUM |
| `server/shared.py` | 58 | 4 | MEDIUM — request validation |

#### `cli/` infrastructure — 7 uncovered files, 48 functions

CLI cmds/ are well-tested (unit tests per command), but CLI infrastructure is not.

| File | Lines | Funcs | Risk |
|------|-------|-------|------|
| `cli/info.py` | 246 | 13 | MEDIUM — `_out`, `_render_result`, `_render_error` |
| `cli/display.py` | 181 | 11 | MEDIUM — Rich rendering functions |
| `cli/decorators.py` | 83 | 4 | MEDIUM — `@with_context`, session/rollback/auto-sync |
| `cli/parser.py` | 277 | 9 | LOW — tested indirectly via CLI tests |
| `cli/dispatch.py` | 133 | 2 | LOW — tested indirectly |
| `cli/bundle_utils.py` | 128 | 8 | MEDIUM — sync helpers, server URL resolution |
| `cli/session.py` | 80 | 6 | MEDIUM — session file read/write |

#### `storage/` — 13 uncovered files, 79 functions

| File | Lines | Funcs | Risk |
|------|-------|-------|------|
| `storage/db/crud_notification.py` | 94 | 5 | MEDIUM |
| `storage/db/ingest.py` | 111 | 10 | HIGH — sync data ingestion |
| `storage/db/crawler.py` | 121 | 3 | MEDIUM |
| `storage/db/session_utils.py` | 43 | 1 | MEDIUM |
| `storage/db/_validators.py` | 101 | 10 | HIGH — input validation used by CRUD |
| `storage/git/guards.py` | 102 | 10 | HIGH — signature + commit guards |
| `storage/git/ops.py` | 142 | 7 | HIGH — git commit/sign operations |
| `storage/git/read.py` | 292 | 16 | MEDIUM — read layer (complex) |
| `storage/git/archive.py` | 52 | 3 | LOW |
| `storage/git/trailers.py` | 63 | 3 | LOW |
| `storage/git/merge.py` | 139 | 10 | MEDIUM |
| `storage/db/state.py` | 81 | 3 | LOW |

### Summary: critical gaps

| Priority | Layer | Files | Functions | Why critical |
|----------|-------|-------|-----------|-------------|
| **P0** | `repl/` | 11 | 75 | Entire REPL has 0% direct coverage |
| **P0** | `core/` | 20 | 101 | Article lifecycle, guards, sync — no direct tests |
| **P0** | `transport/` | 6 | 49 | HTTP client — auth, sync, social — no direct tests |
| **P0** | `server/` | 8 | 33 | API endpoints + auth middleware — no direct tests |
| **P1** | `app/commandspec/` | 3 | 64 | Handler key typos = runtime crash |
| **P1** | `storage/` | 13 | 79 | Git ops, validators, ingest |
| **P2** | `cli/` infra | 7 | 48 | `_out`, display, decorators |

## Audit rounds (ordered by bug risk)

---

## Round 1 — CommandSpec / CLI / REPL parity

**Files:** `app/commandspec/types.py`, `app/commandspec/registry.py`, `app/commandspec/handlers.py`, `cli/parser.py`, `repl/engine.py`, `app/commandspec/schema.py`

### Invariants to verify

| # | Invariant | Existing test? | Action |
|---|-----------|---------------|--------|
| 1.1 | Every `args["key"]` / `args.get("key")` in `handlers.py` appears in the corresponding `CommandSpec.args` | None | Write `test_handler_args_match_spec` |
| 1.2 | CLI `_shared_arg_to_cli` produces valid argparse for every spec | Architecture test covers parser build | OK |
| 1.3 | REPL `_parse_args` handles every ArgSpec type/choices/default correctly | None | Write `test_repl_parse_all_specs` |
| 1.4 | `schema.py` required/default match `ArgSpec` | None | Write `test_schema_matches_spec` |
| 1.5 | CLI and REPL produce identical parsed args for same input | None | Write `test_cli_repl_arg_parity` |
| 1.6 | Every `CommandSpec.cmd_id` is unique | None | Write `test_cmd_ids_unique` |
| 1.7 | No `(group, action)` collision in lookup index | None | Write `test_no_lookup_collisions` |

### Suggested tests

```python
# tests/test_command_spec_consistency.py

def test_handler_args_match_spec():
    """Every args dict key used in handlers must be declared in CommandSpec.args."""
    from peerpedia_core.app.commandspec import COMMAND_GROUPS, TOP_LEVEL_COMMANDS
    import inspect, ast
    ...

def test_cmd_ids_unique():
    ids = [c.cmd_id for g in COMMAND_GROUPS for c in g.commands]
    ids += [c.cmd_id for c in TOP_LEVEL_COMMANDS]
    assert len(ids) == len(set(ids)), f"Duplicate cmd_ids: {[x for x in ids if ids.count(x) > 1]}"

def test_schema_matches_spec():
    """Every command in COMMAND_GROUPS must appear in schema output."""
    from peerpedia_core.app.commandspec.schema import build
    schema = json.loads(build())
    ...
```

---

## Round 2 — Handler args vs registry drift

**Files:** `app/commandspec/handlers.py`, `app/commandspec/registry.py`

### Invariants

| # | Invariant |
|---|-----------|
| 2.1 | Handler functions referenced in `registry.py` exist in `handlers.py` |
| 2.2 | Every required `ArgSpec` key is accessed unconditionally in the handler (not `args.get()`) |
| 2.3 | Handler default values match `ArgSpec.default` |

### Action

Static analysis script that parses each handler function body, extracts `args["X"]` and `args.get("X")` calls, and cross-references with the spec's `ArgSpec` list.

---

## Round 3 — Write operation guards

**Files:** `core/articles/*`, `core/reviews/*`, `core/merge.py`, `core/maintainers.py`, `core/guards.py`, `storage/db/guards.py`

### Invariants

| # | Invariant | Risk |
|---|-----------|------|
| 3.1 | Non-author cannot `edit`/`delete`/`publish` another's article | HIGH |
| 3.2 | Non-maintainer cannot `merge accept` | HIGH |
| 3.3 | Last maintainer cannot be removed from an article | HIGH |
| 3.4 | Review invitation cannot be `accept`-ed twice | MEDIUM |
| 3.5 | Review invitation cannot be `decline`-d after `accept` | MEDIUM |
| 3.6 | Cannot `publish` a deleted article | HIGH |
| 3.7 | Cannot `edit` a published article without maintainer consent | MEDIUM |
| 3.8 | Self-review scores must be valid (1-5 per dimension) | LOW |
| 3.9 | `publish_consents` cleared after publish | MEDIUM |

### Suggested tests

```python
# tests/test_guards_article.py

def test_non_author_cannot_edit():
    """User B cannot edit User A's article."""
    ...

def test_non_maintainer_cannot_accept_merge():
    ...

def test_last_maintainer_cannot_be_removed():
    ...

def test_cannot_accept_review_twice():
    ...
```

---

## Round 4 — Transaction & session safety

**Files:** `cli/decorators.py`, `repl/state.py`, `repl/engine.py`, `server/middleware/db.py`

### Invariants

| # | Invariant |
|---|-----------|
| 4.1 | REPL failed command does not poison next command's session |
| 4.2 | `session_scope()` always closes session (even on exception) |
| 4.3 | CLI `@with_context` always rollbacks on `PeerpediaError` |
| 4.4 | Server `DBSessionMiddleware` does not leak sessions across requests |
| 4.5 | Periodic scan session is isolated from user command session |

### Existing

- `test_repl_failed_command_rollback_does_not_poison_next` — covers 4.1

### Missing

```python
def test_session_scope_closes_on_exception():
    ...

def test_periodic_scan_isolated_from_user_command():
    ...
```

---

## Round 5 — Soft delete consistency

**Files:** `storage/db/crud_user.py`, `storage/db/crud_article.py`, `core/users.py`

### Invariants

| # | Invariant |
|---|-----------|
| 5.1 | Soft-deleted user cannot login |
| 5.2 | Soft-deleted user does not appear in `list_users` / `search_users` |
| 5.3 | Soft-deleted user's articles still appear (they're not deleted) |
| 5.4 | Soft-deleted user cannot be followed |
| 5.5 | Deleted article does not appear in `list_articles` (unless explicit) |
| 5.6 | Deleted article's reviews still exist |
| 5.7 | `count_articles` matches `list_articles` length |

### Suggested

```python
def test_deleted_user_cannot_login():
    ...

def test_deleted_user_not_in_search():
    ...

def test_deleted_article_not_in_list():
    ...
```

---

## Round 6 — Client/server protocol matching

**Files:** `transport/http/articles.py`, `transport/http/social.py`, `server/routes/articles.py`, `server/routes/users.py`

### Invariants

| # | Invariant |
|---|-----------|
| 6.1 | Every `_fetch_*` / `_push_*` in transport has a matching server route |
| 6.2 | Request body field names match server `_require_field` names |
| 6.3 | Response shape parsing matches server response shape |
| 6.4 | Auth header is sent by client and verified by server on every non-public route |
| 6.5 | Clock skew check happens before processing |

### Action

Manual diff of request/response shapes. Highest-value: compare `transport/http/articles.py` ↔ `server/routes/articles.py`.

---

## Round 7 — State machine enforcement

### Article status

```
draft → sedimentation (on publish)
sedimentation → published (after sink + approvals)
sedimentation → draft (on rollback)
published → (cannot go back)
any → deleted
```

### Review invitation

```
none → invited (on invite)
invited → accepted / declined
accepted → submitted
```

### Merge proposal

```
none → open (on propose)
open → accepted / withdrawn
```

### Action

For each state machine:
1. List all legal transitions
2. Verify guards exist for each illegal transition
3. Write one test per illegal transition

---

## Round 8 — Boundary & edge values

### Cases to test

| Category | Examples |
|----------|---------|
| Empty inputs | `""` title, `""` comment, `""` name |
| Score boundaries | 0, 6, negative, float for int field |
| Pagination | `limit=0`, `limit=10000`, `offset < 0` |
| ID ambiguity | Prefix matching multiple articles/users |
| Unicode | Non-ASCII names, emoji in content |
| Very long strings | 10KB title, 1MB content |
| Duplicate actions | follow twice, bookmark twice, share twice |
| Concurrent-like | Rapid publish + delete |

---

## Execution order

```
Week 1: Round 1 (CommandSpec parity) — highest bug probability
Week 2: Round 3 (write guards) — highest severity
Week 3: Round 5 (soft delete) + Round 4 (session safety)
Week 4: Round 6 (protocol matching) + Round 7 (state machines)
Week 5: Round 8 (boundary values)
```

## Output format for each finding

```markdown
### Bug: [title]
- **Severity**: critical / high / medium / low
- **Files**: ...
- **Reproduction**: `peerpedia ...`
- **Root cause**: ...
- **Fix**: ...
- **Test**: `def test_...`
```

---

## Round 9 — Red-team user journeys (malicious / careless actor simulation)

> Assume the role of a user trying to break invariants.
> Each journey = a sequence of CLI/REPL commands that should be impossible or should fail gracefully.
> These are TEST SCENARIOS only — do not modify any code.

### Personas

| Persona | Goal |
|---------|------|
| **Alice** | Normal author, owns article `art-alice` |
| **Bob** | Malicious actor, wants to corrupt Alice's work |
| **Carol** | Careless reviewer, does things in wrong order |
| **Dave** | Deleted user, tries to use the system post-deletion |
| **Eve** | Sync attacker, tries to poison peer data |
| **Mallory** | Boundary abuser, submits extreme inputs |
| **Forky** | Fork spammer, creates infinite forks |
| **Ghost** | Unauthenticated user, tries to access everything |

---

### Journey 9.1 — Bob the article saboteur

**Objective:** Bob wants to destroy Alice's article without permission.

```
# Alice creates and publishes
Alice:  register --name "Alice"
Alice:  article create --title "My Research" --publish --scores "orig=4,rigor=4,comp=4,ped=4,imp=4"

# Bob registers and tries to mess with Alice's article
Bob:    register --name "Bob"
Bob:    article edit art-alice --title "GARBAGE"        # ← MUST FAIL: not author
Bob:    article delete art-alice --force                # ← MUST FAIL: not author
Bob:    article publish art-alice --scores "orig=1,rigor=1,comp=1,ped=1,imp=1"  # ← MUST FAIL: not author
Bob:    fork art-alice                                  # ← OK (forking published articles is allowed)
Bob:    merge propose fork-bob --target art-alice        # ← Bob proposes merge into Alice's article
```

**Invariants to check:**
- Non-author cannot `edit`, `delete`, or `publish` another's article
- After Bob's failed attempts, Alice's article is unchanged
- Bob's fork is a separate article (different id)
- Does Bob's merge proposal require Alice's consent? (check guards)

**Suggested tests:**
```python
def test_non_author_cannot_edit_others_article():
def test_non_author_cannot_delete_others_article():
def test_non_author_cannot_publish_others_article():
def test_article_unchanged_after_failed_attacks():
```

---

### Journey 9.2 — Bob the maintainer trickster

**Objective:** Alice adds Bob as maintainer (co-author). Bob abuses this trust.

```
# Alice adds Bob as co-author
Alice:  maintainer add art-alice --target-user Bob

# Bob as maintainer:
Bob:    article edit art-alice --title "Bob Was Here"   # ← OK (maintainer can edit)
Bob:    maintainer remove art-alice --target-user Alice  # ← MUST FAIL? (last maintainer?)
Bob:    maintainer add art-alice --target-user Mallory   # ← can Bob add arbitrary maintainers?
Bob:    article delete art-alice --force                # ← can maintainer delete?
```

**Invariants to check:**
- Can a maintainer remove the original author?
- Can a maintainer remove ALL other maintainers (leaving only themselves)?
- Can a maintainer delete the article?
- Can a maintainer add arbitrary third parties as maintainers?

**Suggested tests:**
```python
def test_maintainer_cannot_remove_last_other_maintainer():
def test_maintainer_permissions_boundary():
```

---

### Journey 9.3 — Carol the careless reviewer

**Objective:** Carol does review operations in illegal orders and with invalid data.

```
# Alice publishes, Carol registers
Carol:  register --name "Carol"

# Carol tries to review without being invited
Carol:  review submit art-alice --scores "orig=3,rigor=3,comp=3,ped=3,imp=3" --comment "..."  # ← MUST FAIL: not invited

# Alice invites Carol
Alice:  review invite art-alice --user Carol

# Carol accepts twice
Carol:  review accept art-alice       # ← OK
Carol:  review accept art-alice       # ← MUST FAIL: already accepted

# Carol declines after accepting
Carol:  review decline art-alice      # ← MUST FAIL: already accepted

# Carol submits invalid scores
Carol:  review submit art-alice --scores "" --comment "..."                # ← MUST FAIL: empty scores
Carol:  review submit art-alice --scores "orig=6" --comment "..."          # ← MUST FAIL: score > 5
Carol:  review submit art-alice --scores "orig=0" --comment "..."          # ← MUST FAIL: score < 1
Carol:  review submit art-alice --scores "fake=5" --comment "..."          # ← MUST FAIL: unknown dimension
Carol:  review submit art-alice --scores "orig=5" --comment ""             # ← should this fail? min 200 chars
Carol:  review submit art-alice --scores "orig=5" --comment "Short"        # ← should this fail? < 200 chars

# Carol submits valid review, then tries to submit again
Carol:  review submit art-alice --scores "orig=4,rigor=3,comp=4,ped=3,imp=4" --comment "Good paper, well argued with solid methodology and clear results."
Carol:  review submit art-alice --scores "orig=1,rigor=1,comp=1,ped=1,imp=1" --comment "..."  # ← MUST FAIL or UPSERT: already submitted

# Carol rates a review that doesn't exist
Carol:  review rate art-alice --reviewer Dave --helpfulness 5  # ← MUST FAIL: Dave has no review
```

**Invariants to check:**
- Invitation required before submitting review
- Cannot accept twice / decline after accept
- Score validation: range 1-5, known dimensions only
- Comment minimum length enforced
- Cannot submit multiple reviews for same article
- Cannot rate non-existent review

**Suggested tests:**
```python
def test_cannot_review_without_invitation():
def test_cannot_accept_invitation_twice():
def test_cannot_decline_after_accept():
def test_review_scores_range_validated():
def test_review_comment_length_validated():
def test_cannot_submit_duplicate_review():
def test_cannot_rate_nonexistent_review():
```

---

### Journey 9.4 — Dave the ghost (deleted user)

**Objective:** Dave deletes his account, then tries to keep using PeerPedia.

```
Dave:   register --name "Dave"
Dave:   article create --title "Dave's Paper" --publish --scores "orig=3,rigor=3,comp=3,ped=3,imp=3"
Dave:   follow Alice
Dave:   account delete
# Account deleted — now Dave tries:
Dave:   login --name "Dave"                              # ← MUST FAIL: soft-deleted
Alice:  follow Dave                                      # ← MUST FAIL? can you follow a deleted user?
Alice:  article show dave-art-id                         # ← should Dave's article still be visible?
```

**Invariants to check:**
- Deleted user cannot login
- Deleted user's articles still exist (not cascade-deleted)
- Can others follow a deleted user?
- Does `school` / `search` show deleted users?

**Suggested tests:**
```python
def test_deleted_user_cannot_login():
def test_deleted_user_articles_still_accessible():
def test_cannot_follow_deleted_user():
def test_deleted_user_not_in_search_or_school():
```

---

### Journey 9.5 — Eve the sync poisoner

**Objective:** Eve runs her own PeerPedia server and tries to poison Alice's data through sync.

```
# Alice sets up
Alice:  register --name "Alice"
Alice:  article create --title "Original" --publish --scores "orig=4,rigor=4,comp=4,ped=4,imp=4"

# Eve runs a malicious server at evil.example.com
# Alice accidentally syncs from Eve's server
Alice:  sync pull --server https://evil.example.com      # ← what happens? crash? timeout? forged data?
Alice:  sync discover --server https://evil.example.com   # ← does it ingest fake users/articles?

# Eve sends malformed bundles
# (requires HTTP-level testing — send invalid git bundle, truncated data, wrong article_id)

# Eve sends articles with fake author signatures
# (requires TOFU verification check — does sync verify commit signatures?)
```

**Invariants to check:**
- Sync from untrusted server does not corrupt local data
- Malformed bundle is rejected (not partially applied)
- Commit signatures verified on sync
- TOFU public key not overwritten by sync
- Clock skew violation blocks sync

**Suggested tests:**
```python
def test_sync_rejects_malformed_bundle():
def test_sync_verifies_commit_signatures():
def test_sync_clock_skew_blocked():
def test_sync_does_not_overwrite_tofu_key():
def test_sync_unknown_server_graceful_failure():
```

---

### Journey 9.6 — Mallory the boundary abuser

**Objective:** Mallory submits extreme inputs to find crashes and bypasses.

```
Mallory: register --name ""                              # ← MUST FAIL: empty name
Mallory: register --name "A" * 1000                      # ← very long name
Mallory: register --name "../../../etc/passwd"           # ← path traversal attempt in name
Mallory: register --name "<script>alert(1)</script>"     # ← XSS attempt (should be harmless in CLI)
Mallory: register --name "'; DROP TABLE users; --"       # ← SQL injection attempt

# After registering normally:
Mallory: article create --title ""                        # ← MUST FAIL: empty title
Mallory: article create --title "x" --content "A" * 10000000  # ← 10MB content
Mallory: article create --title "x" --format "evil"       # ← MUST FAIL: unknown format
Mallory: article create --title "x" --publish --scores "orig=999999999999" # ← huge score
Mallory: article edit art-id --title "$(rm -rf /)"        # ← command injection in title

# Pagination abuse:
Mallory: article list --limit 0                            # ← zero limit
Mallory: article list --limit -1                           # ← negative limit
Mallory: article list --limit 999999                       # ← huge limit

# ID abuse:
Mallory: article show ""                                   # ← empty id
Mallory: article show "../../etc/passwd"                   # ← path traversal
Mallory: article edit "" --title "x"                       # ← empty id for edit

# Sync abuse:
Mallory: sync discover --depth 999 --max-users 999999      # ← huge values
```

**Invariants to check:**
- Empty required fields rejected
- Format/choices validated
- Score range enforced
- Limits bounded or handled gracefully
- No crashes on extreme inputs
- No injection through article/user names (Rich markup escaping)

**Suggested tests:**
```python
def test_empty_name_rejected():
def test_empty_title_rejected():
def test_invalid_format_rejected():
def test_score_overflow_handled():
def test_limit_zero_handled():
def test_limit_negative_handled():
def test_extreme_content_size_handled():
```

---

### Journey 9.7 — Forky the fork spammer

**Objective:** Forky creates chaos through excessive forking and merge proposals.

```
Forky:  register --name "Forky"
Forky:  fork art-alice                                   # ← fork #1
Forky:  fork art-alice                                   # ← fork #2 (can same user fork twice?)
Forky:  fork forky-fork-1                                # ← fork of a fork? (fork chain)
Forky:  merge propose forky-fork-1 --target art-alice     # ← propose merge
Forky:  merge propose forky-fork-1 --target art-alice     # ← duplicate proposal?
Forky:  merge withdraw proposal-1                         # ← OK
Forky:  merge propose forky-fork-1 --target art-alice     # ← re-propose after withdraw?
Forky:  merge propose forky-fork-1 --target nonexistent   # ← MUST FAIL: target doesn't exist
```

**Invariants to check:**
- Can same user fork the same article twice?
- Can you fork a fork? (chain depth)
- Duplicate merge proposals?
- Re-propose after withdraw?
- Propose to non-existent target

**Suggested tests:**
```python
def test_cannot_fork_same_article_twice():
def test_fork_chain_depth():
def test_cannot_duplicate_merge_proposal():
def test_can_repropose_after_withdraw():
def test_merge_propose_nonexistent_target_rejected():
```

---

### Journey 9.8 — Ghost the unauthenticated snooper

**Objective:** Ghost has no account but tries to access everything via CLI and REPL.

```
# CLI without login:
Ghost$  peerpedia article list                            # ← public articles only?
Ghost$  peerpedia article show art-alice                  # ← public article content?
Ghost$  peerpedia article create --title "Spam"            # ← MUST FAIL: not logged in
Ghost$  peerpedia follow Alice                            # ← MUST FAIL: not logged in
Ghost$  peerpedia review submit art-alice ...              # ← MUST FAIL: not logged in
Ghost$  peerpedia account whoami                           # ← shows "not logged in"?
Ghost$  peerpedia sync pull                                # ← MUST FAIL: not logged in?
Ghost$  peerpedia notifications                            # ← MUST FAIL: not logged in
Ghost$  peerpedia school                                   # ← public?
Ghost$  peerpedia schema                                   # ← public?

# REPL without login:
Ghost>  article create --title "x"                         # ← MUST FAIL
Ghost>  :user Alice                                        # ← can resolve public user info?
Ghost>  :school                                            # ← public?
Ghost>  :feed                                              # ← MUST FAIL: no user
```

**Invariants to check:**
- Write operations require authentication
- Read operations may be partially public
- Server endpoints have correct auth middleware (skip list)
- REPL gracefully handles unauthenticated state

**Suggested tests:**
```python
def test_unauthenticated_cannot_create_article():
def test_unauthenticated_cannot_follow():
def test_unauthenticated_can_list_public_articles():
def test_unauthenticated_school_accessible():
def test_unauthenticated_repl_rejects_write_commands():
```

---

### Journey 9.9 — Mallory the race-condition hunter

**Objective:** Mallory runs commands rapidly to trigger race conditions.

```
# Rapid duplicate actions:
Mallory: follow Alice      # (run twice in quick succession)
Mallory: unfollow Alice    # (run twice)
Mallory: bookmark add art-alice  # (run twice)
Mallory: bookmark remove art-alice  # (run twice, idempotent?)
Mallory: share add art-alice  # (run twice)
Mallory: share remove art-alice  # (run twice)

# Rapid state transitions:
Mallory: article publish art-mallory --scores "..."  # ← run twice
Mallory: article delete art-mallory --force          # ← then immediately article show

# Rapid maintainer changes:
Mallory: maintainer add art-alice --target-user Bob
Mallory: maintainer remove art-alice --target-user Bob  # ← immediately after add
Mallory: maintainer add art-alice --target-user Bob     # ← immediately after remove
```

**Invariants to check:**
- Follow/unfollow idempotent
- Bookmark add/remove idempotent
- Share add/remove idempotent
- Cannot publish already-published article
- Deleted article accessed immediately after delete

**Suggested tests:**
```python
def test_follow_idempotent():
def test_unfollow_idempotent():
def test_bookmark_add_idempotent():
def test_cannot_publish_already_published():
def test_deleted_article_immediately_inaccessible():
```

---

### Journey 9.10 — Carol the alias abuser

**Objective:** Carol uses aliases to confuse the system.

```
Carol:  register --name "Carol"
Alice:  register --name "Alice"
Bob:    register --name "Bob"

Carol:  follow Alice
Carol:  alias set Alice --alias "Alice"                   # ← alias same as real name?
Carol:  alias set Alice --alias "Bob"                     # ← alias same as another user?
Carol:  alias set Alice --alias ""                        # ← empty alias?
Carol:  alias set Alice --alias "x" * 100                 # ← very long alias?
Carol:  alias set Alice --alias "friend"
Carol:  alias set Alice --alias "friend"                  # ← duplicate alias?
Carol:  alias set Bob --alias "friend"                    # ← same alias for different user?
Carol:  alias remove Alice                                # ← OK
Carol:  alias remove Alice                                # ← remove twice?

# Try to follow/unfollow via alias:
Carol:  follow friend                                     # ← should resolve to Alice?
Carol:  unfollow friend                                   # ← should resolve to Alice?
Carol:  alias remove Alice                                # ← remove after using
```

**Invariants to check:**
- Alias cannot be empty
- Alias cannot match real name of another user?
- Duplicate alias for same user?
- Same alias for different users?
- Follow/unfollow via alias works
- Remove idempotent

**Suggested tests:**
```python
def test_alias_cannot_be_empty():
def test_alias_same_name_as_self_allowed():
def test_alias_same_name_as_other_user():
def test_alias_duplicate_idempotent():
def test_same_alias_for_different_users():
def test_follow_via_alias():
def test_alias_remove_idempotent():
```

---

### Journey 9.11 — Eve the protocol mismatch attacker

**Objective:** Eve crafts HTTP requests that don't match the client, exploiting server-side gaps.

```
# Send requests with missing required headers
POST /api/articles         # ← no Auth header → 401?
POST /api/articles         # ← Auth header with wrong method → 401?
POST /api/articles         # ← Auth header with wrong body hash → 401?
POST /api/articles         # ← Auth header with expired timestamp → 401?
POST /api/articles         # ← Auth header with future timestamp → 401?
POST /api/articles         # ← Auth header with wrong user_id → 401?

# Send requests with mismatched body
POST /api/sync             # ← body missing required fields
POST /api/sync             # ← body with extra unknown fields
POST /api/sync             # ← body with wrong types

# Send requests to wrong endpoints
GET  /api/articles/id      # ← wrong method
POST /api/nonexistent       # ← 404?

# Send oversized payloads
POST /api/sync             # ← 100MB bundle
POST /api/articles         # ← 1MB title
```

**Invariants to check:**
- All protected routes reject missing/invalid auth
- Body validation rejects malformed payloads
- Unknown fields don't cause crashes
- Payload size limits enforced

**Suggested tests:**
```python
def test_server_rejects_missing_auth():
def test_server_rejects_wrong_method_in_signature():
def test_server_rejects_expired_timestamp():
def test_server_rejects_malformed_body():
def test_server_handles_unknown_fields():
def test_server_enforces_payload_size_limits():
```

---

### Summary: red-team journey coverage map

| Journey | Persona | Target | Severity |
|---------|---------|--------|----------|
| 9.1 | Bob | Article ownership guards | CRITICAL |
| 9.2 | Bob | Maintainer permission escalation | CRITICAL |
| 9.3 | Carol | Review state machine + validation | HIGH |
| 9.4 | Dave | Soft-delete consistency | HIGH |
| 9.5 | Eve | Sync data integrity | CRITICAL |
| 9.6 | Mallory | Input validation + injection | MEDIUM |
| 9.7 | Forky | Fork/merge idempotency | MEDIUM |
| 9.8 | Ghost | Auth boundary enforcement | HIGH |
| 9.9 | Mallory | Race conditions | MEDIUM |
| 9.10 | Carol | Alias resolution edge cases | LOW |
| 9.11 | Eve | Server protocol hardening | HIGH |

---

## Coverage improvement roadmap

### P0 — immediately (zero coverage, high impact)

#### `repl/engine.py` — arg parser

```python
# tests/repl/test_engine_parse.py
def test_parse_args_positional():
    """_parse_args assigns positional args in ArgSpec order."""

def test_parse_args_flag_bool():
    """takes_value=False → True when present, False when absent."""

def test_parse_args_flag_value():
    """--key=value and --key value both work."""

def test_parse_args_type_coercion_int():
    """type=int coerces '42' → 42."""

def test_parse_args_choices_rejected():
    """value not in choices → PeerpediaError."""

def test_parse_args_default_applied():
    """ArgSpec.default used when arg not provided."""

def test_parse_args_peeredia_server_env():
    """PEERPEDIA_SERVER env var fills 'server' arg when empty."""

def test_execute_unknown_command():
    """Unknown command prints error, returns True (continue REPL)."""

def test_execute_session_scope_commits():
    """Successful command commits. Session closed after."""

def test_execute_session_scope_rollbacks():
    """Failed command rollbacks. Session closed after."""
```

#### `repl/state.py` — session management

```python
# tests/repl/test_state_session.py
def test_new_session_returns_fresh_session():
    """Each call to new_session() returns a different session."""

def test_session_scope_commits_on_success():
    """with session_scope() as db: ... → db.commit() called."""

def test_session_scope_rollbacks_on_exception():
    """Exception inside with session_scope() → db.rollback() called."""

def test_session_scope_closes_after_exception():
    """Session is closed even after exception."""

def test_close_db_disposes_engine():
    """close_db() calls engine.dispose()."""
```

#### `core/articles/` — article lifecycle

```python
# tests/core/test_article_lifecycle.py
def test_create_article_with_content():
    """Article created in git + DB."""

def test_publish_article_generates_notifications():
    """Publishing generates notifications for maintainers."""

def test_publish_article_validates_self_review():
    """Invalid self-review scores → rejected."""

def test_delete_article_soft_deletes():
    """Deleted article not in default list, but still in DB."""

def test_rollback_article_restores_state():
    """Rollback to previous commit restores content + status."""

def test_fork_article_creates_draft():
    """Fork of published article is draft, different id."""

def test_sink_auto_publishes():
    """Article in sedimentation → auto-published after duration."""
```

#### `transport/` — HTTP client

```python
# tests/transport/test_auth.py
def test_sign_auth_header_format():
    """Auth header has format: Peerpedia <uid>:<ts>:<body_sha256>:<sig>"""

def test_build_auth_header_skips_when_no_key():
    """Returns None when private_key_bytes is None."""

# tests/transport/test_client_server_match.py
def test_article_endpoints_match():
    """Every _fetch_* in transport/http/articles.py has matching server route."""

def test_social_endpoints_match():
    """Every _fetch_* / _push_* in transport/http/social.py has matching server route."""
```

#### `server/` — API endpoints

```python
# tests/server/test_auth_middleware.py
def test_missing_auth_header_returns_401():
    """Request without Authorization header → 401."""

def test_invalid_signature_returns_401():
    """Wrong signature → 401."""

def test_expired_timestamp_returns_401():
    """Timestamp outside ±30s window → 401."""

def test_public_routes_skip_auth():
    """school, following, followers, articles routes skip auth."""
```

### P1 — next (zero coverage, medium impact)

#### `app/commandspec/` — command spec consistency

```python
# tests/app/test_command_spec.py
def test_handler_args_match_spec():
    """Every args['key'] / args.get('key') in handlers.py exists in registry ArgSpec."""

def test_cmd_ids_unique():
    """No duplicate cmd_id across COMMAND_GROUPS + TOP_LEVEL_COMMANDS."""

def test_find_spec_lookup():
    """find_spec('article', 'create') returns correct CommandSpec."""

def test_schema_output_contains_all_commands():
    """schema.build() includes every command in COMMAND_GROUPS."""

def test_schema_required_matches_spec():
    """schema 'required' list matches ArgSpec.required."""
```

#### `core/guards.py` — commit + signature verification

```python
# tests/core/test_guards.py
def test_verify_commit_signature_and_tofu():
    """Valid signature + matching pubkey → passes."""

def test_verify_commit_signature_wrong_key():
    """Signature doesn't match pubkey → fails."""

def test_tofu_key_not_overwritten():
    """Second sync with different pubkey for same user → TOFU violation."""

def test_guard_closes_trailer():
    """Commit message with Closes: <valid ref> → OK."""
```

#### `storage/git/` — git operations

```python
# tests/storage/test_git_ops.py
def test_commit_article_signing():
    """commit_article with signing key → signed commit."""

def test_commit_article_unsigned():
    """commit_article without signing key → unsigned commit."""

def test_init_article_repo_creates_git_dir():
    """init_article_repo creates a valid git repo."""

def test_get_head_hash_returns_commit():
    """get_head_hash returns hex SHA of HEAD."""
```

### P2 — later (indirect coverage, lower risk)

- `cli/info.py`: `_out`, `_render_result`, `_render_error` — tested indirectly via CLI tests
- `cli/display.py`: rendering functions — tested indirectly
- `repl/display.py`: `render_result`, `render_error` — visual output, hard to test
- `repl/browse.py`: TUI browsers — hard to unit-test, best tested manually
- `presentation/rich/components.py`: pure rendering, low bug risk

### Coverage target

| Milestone | Tests | Coverage gain |
|-----------|-------|--------------|
| **Now** | 949 | Baseline (app commands, CLI cmds, architecture) |
| + P0 | ~1,050 | repl engine, core articles, transport auth, server middleware |
| + P1 | ~1,100 | commandspec consistency, core guards, git ops |
| + P2 | ~1,120 | CLI infra, repl display |
