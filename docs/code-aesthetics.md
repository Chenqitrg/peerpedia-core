# Code Aesthetics — Patterns from the 2026-06 Refactor

## 1. CRUD idempotency: commands layer is pure orchestration

Commands functions should NOT check "does this already exist?" before calling CRUD.
Push idempotency into the CRUD layer, then commands becomes:

```
validate input → call idempotent CRUD → return count
```

**Before** (discover.py, 25 lines):
```python
def ingest_bookmarks(db, user_id, entries):
    _require_keys(entries, "article_id", label="bookmarks")
    added = 0
    for e in entries:
        if is_bookmarked(db, user_id, e["article_id"]):  # ← CRUD already does this
            logger.warning("...")                         # ← noise
            continue
        add_bookmark(db, user_id, e["article_id"])
        added += 1
    db.flush()
    return added
```

**After** (4 lines):
```python
def ingest_bookmarks(db, user_id, entries):
    _require_keys(entries, "article_id", label="bookmarks")
    for e in entries:
        add_bookmark(db, user_id, e["article_id"])
    return len(entries)
```

New CRUD functions added for this pattern:
- `ensure_user` — idempotent user creation with address conflict check
- `ensure_article_stub` — idempotent article stub from peer data
- `ensure_notification` — dedup by 5-field key
- `set_user_pubkey_tofu` — TOFU pubkey with return status
- `create_user_stub` — made idempotent (was "caller must ensure not exists")

## 2. `require_*` — fail fast on missing resources

Replace `get_X + if None: raise` with single-purpose guard functions:

```python
# Before
article = get_article(db, article_id)
if article is None:
    raise FileNotFoundError(f"Article not found: {article_id}")

# After
article = require_article(db, article_id)
```

Added:
- `require_article_repo(article_id)` — returns Path or raises NotFoundError
- `require_review_scores(rp, dir_name, article_id)` — returns dict or raises
- `authorize_article_action(db, article_id, user_id)` — returns (user, article, mids), checks fold

When the resource is legitimately optional, catch the exception:
```python
try:
    rp = require_article_repo(article_id)
    require_article(db, article_id)
except NotFoundError:
    return  # silent no-op for integrity guard
```

## 3. One canonical function per concept

When the same logic appears in 3+ places, extract it once.

| Function | Location | Replaces |
|---|---|---|
| `article_repo_path(id)` | `config/paths.py` | 28× `DEFAULT_ARTICLES_DIR / article_id` |
| `is_platform_commit(email)` | `types/status.py` | 5× `email == PLATFORM_EMAIL` |
| `read_status_from_git(rp)` | `git_backend.py` | 2× inline git traversal |
| `require_commit_pubkey_signature(...)` | `git_backend.py` | 3× "extract pubkey → check → verify" |
| `resolve_article_format(rp)` | `git_backend.py` | 4× `.md`/`.typ` detection |
| `article_format_to_ext(fmt)` | `config/params.py` | 5× `".typ" if fmt == "typst" else ".md"` |
| `article_filename(ext)` | `config/params.py` | 5× `f"article{ext}"` |
| `extract_user_id_from_email(email)` | `config/params.py` | 4× `email.split("@")[0]` |
| `rebuild_db_from_git(db, id)` | `integrity.py` | sync + repair paths unified |

## 4. No direction strings in CRUD

A `direction: str` parameter with `if direction == "following"` branching means the function
doesn't know what it does. Split into separate functions with explicit signatures:

```
                   forward (I→them)     backward (they→me)
insert (batch)     follow_users         add_followers
replace (batch)    set_following        set_followers
```

Commands layer maps the concept to the right CRUD call:
```python
def sync_following(db, follower_id, entries):
    ids = _validate_follow_entries(entries, follower_id, "following")
    added = follow_users(db, follower_id, ids)
    set_following(db, follower_id, ids)
    return added
```

## 5. Phase labels > inline comments

Long functions get named phases with `# ──` separators. Each phase is 2-7 lines
delegating to helpers:

```python
def publish_article(...):
    # ── Authorization ──
    user, a, mids = authorize_article_action(db, article_id, user_id)
    assert_can_publish_article(a, mids, user)

    # ── Validation ──
    validate_self_review_scores(self_review)
    _check_sedimentation_limit(db, user_id)

    # ── Write + commit ──
    write_review_to_git(...)
    commit_hash = commit_status_marker(rp, "sedimentation")

    # ── Update DB ──
    update_article_status(db, article_id, "sedimentation")
    ...

    # ── Notify ──
    batch = _build_publish_notifications(...)
```

Extract helpers serve exactly one phase and return immediately after.

## 6. Eliminate circular imports

Lazy imports (`from X import Y` inside function body) signal a circular dependency.
Fix by importing from a lower-level module that doesn't participate in the cycle:

```python
# Before — circular: integrity → commands.articles → integrity
from peerpedia_core.commands.articles import rebuild_article_authors  # lazy

# After — _helpers doesn't import integrity
from peerpedia_core.commands.articles._helpers import rebuild_article_authors  # top-level
```

Same fix for `bundle.py ↔ integrity.py`: move shared functions (`sync_reviews_from_worktree`,
`sync_status_from_git`) into `integrity.py`, break the cycle entirely.

## 7. `ingest_*` vs `sync_*` — behavior in the function name

- `ingest_*` — insert only, never delete (peer discovery)
- `sync_*` — insert + soft-delete stale entries (home-server authoritative)

No `authoritative: bool` parameter. The caller chooses the right function:

```python
# exchange.py
if home_server is not None and server == home_server:
    return sync_following(db, user_id, data)
return ingest_following(db, user_id, data)
```

## 8. `_validate_*` — shared validation, separate actions

When multiple functions share validation but differ in actions, extract just the validation:

```python
def _validate_follow_entries(entries, source_id, label) -> set[str]:
    _require_keys(entries, "id", label=label)
    remote_ids = {e["id"] for e in entries}
    if source_id in remote_ids:
        raise ValueError(f"{label}: self-follow detected")
    return remote_ids
```

Each public function then calls the right actions explicitly — no internal branching.

## 9. Thin orchestration: main function as a story

The main function should read like a story with named steps. No nested try/except,
no inline model construction, no raw DB queries:

```python
def apply_sync_bundle(db, article_id, *, ff_only=True):
    rp = require_article_repo(article_id)
    old_head = get_head_or_none(rp)
    new_head = merge_fetch_head(rp, ff_only=ff_only)

    try:
        if old_head:
            _verify_new_commits(db, rp, since_hash=old_head)
        rebuild_db_from_git(db, article_id)
    except Exception:
        _try_rollback(rp, old_head, new_head)
        raise

    return new_head
```

## 10. What we deleted

- **Redundant guards**: `is_bookmarked` + `add_bookmark` (CRUD already idempotent)
- **Redundant maintainer checks**: sync won't create articles without maintainers
- **Dead code**: `old_status == "draft"` branch when draft is already asserted
- **Warnings for normal cases**: "already bookmarked — skipping" (idempotency is normal)
- **Lazy imports**: all eliminated from integrity.py, bundle.py, discover.py
- **`DEFAULT_ARTICLES_DIR / article_id`**: 4 occurrences replaced with `article_repo_path` or `require_article_repo`
- **Inline format detection**: `".typ" if fmt == "typst" else ".md"` → `article_format_to_ext`
- **`nullcontext` for signing**: 5 occurrences of `if signing_key: with... else: commit_article(...)` collapsed

## Summary

Every function should do exactly one thing. If you see `if/else` branching on a
parameter value, split the function. If you see `get_X + check None + raise`,
use `require_X`. If you see the same pattern in 3+ places, extract a canonical
function. CRUD functions should be idempotent. Commands functions should be thin
orchestration. No lazy imports.
