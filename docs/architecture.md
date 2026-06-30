# PeerPedia Core — Architecture

> **Note**: This architecture was refactored in v0.5.x. The previous flat `commands/`, `policies/`, `bundle/`, `social/` directories were reorganized into `cli/` → `app/` → `core/` with `server/` separated from `transport/`. The `workflow/` directory was renamed to `compute/`. See git history for the full migration.

## Layer Stack

```
cli/          User commands — thin pass-through to app/; imports core/ + transport/, never storage/
  ↓
app/          Command facades — context building, ref resolution, result formatting (AppResult)
  ↓
core/         Orchestration — business logic merging transport + storage (sync_article, publish, review…)
  ↓
transport/    P2P protocol — Transport dataclass bundles HTTP callbacks
  http/       HTTP implementation — ONLY layer importing httpx (_core.py)
storage/      Git backend (git/) + DB (db/) + local files (peers.py)
server/       HTTP server — Starlette routes + middleware; imports core/, never transport/http/
config/       Constants + tunable params (params.py)
compute/      Pure compute — scoring, reputation, sedimentation (no IO)
types/        Domain type definitions — scores, status, entities (zero deps)
```

## File Tree

```
peerpedia_core/
├── __main__.py                # Top-level router — CLI or REPL (only module aware of both)
├── compiler.py               # Compiler backend (Markdown/Typst → HTML/PDF/SVG/PNG)
├── crypto.py                  # Ed25519 key derivation, signing, verification
├── editor.py                  # $EDITOR integration + commit message prompts
├── exceptions.py              # Semantic exceptions
├── frontmatter.py             # YAML frontmatter parse/build
├── messages.py               # Centralized message registry (176 user-facing messages)
├── names.py                   # Anonymous reviewer display names
├── time.py                    # Clock utilities (skew detection, monotonic time)

├── config/
│   ├── paths.py               # Filesystem paths (PEERPEDIA_HOME env override)
│   ├── git.py                 # Git config helpers (gitignore, SSH signing env)
│   └── params.py              # Tunable parameters (sink days, score weights, rate limits)

├── types/
│   ├── scores.py              # FiveDimScores, ReputationScores, SCORE_DIMENSIONS
│   ├── status.py              # Article/workflow status constants
│   └── entities.py            # ArticleRecord, ReviewRecord, UserStub dataclasses

├── rules/                     # Authorization — permission checks, no IO
│   ├── articles.py            # Article permissions (read/write/fork/publish/review/merge)
│   └── reviews.py             # Review permissions (submit/rate/reply)

├── app/                       # Command facade layer — context, refs, result types
│   ├── context.py             #   AppContext (db + transport + session)
│   ├── parsers.py             #   Input parsers (scores, refs)
│   ├── refs.py                #   require_article, require_user, require_user_by_ref
│   ├── result.py              #   AppResult / AppNotice dataclasses
│   └── commands/
│       ├── account.py         #     register, login, whoami, search_users, bootstrap
│       ├── article.py         #     create, show, list, edit, publish, delete, diff, fork
│       ├── bundle.py          #     sync status, push, pull, discover
│       ├── dashboard.py       #     count_user_articles, count_users, publish_ready
│       ├── display.py         #     Data lookups for CLI rendering (never from core/ directly)
│       ├── fork.py            #     fork + merge proposal operations
│       ├── maintainer.py      #     add/remove/list maintainers, consent/revoke
│       ├── notification.py    #     list/mark_read notifications
│       ├── review.py          #     submit, list, reply, invite, accept, decline, rate
│       ├── social.py          #     follow, unfollow, following, followers, school, bookmark, share, alias
│       └── sync.py            #     sync_and_discover orchestration

├── core/                      # Business logic — imports transport/ + storage/
│   ├── __init__.py            #   Facade: re-exports all public functions + db_session
│   ├── users.py               #   User lifecycle + follow/unfollow
│   ├── views.py               #   Response-ready dicts (get_user_view, get_following_views, …)
│   ├── guards.py              #   Shared guard helpers
│   ├── bookmarks.py           #   Bookmark operations
│   ├── shares.py              #   Share operations
│   ├── maintainers.py         #   Maintainer operations
│   ├── merge.py               #   Merge proposal lifecycle
│   ├── notifications.py       #   Notification operations
│   ├── sync_article.py        #   Article sync orchestration (k-exponential probe protocol)
│   ├── sync_social.py         #   Social graph sync (discover_following, discover_followers)
│   ├── articles/
│   │   ├── __init__.py        #     Read wrappers + re-exports
│   │   ├── _helpers.py        #     require_article, rebuild_article_authors, _reset_sink
│   │   ├── create.py          #     create_article_with_content
│   │   ├── update.py          #     update_article_content
│   │   ├── publish.py         #     publish_article
│   │   ├── fork.py            #     fork_article
│   │   ├── rollback.py        #     rollback_article
│   │   ├── delete.py          #     delete_article
│   │   ├── diff.py            #     diff_article + resolve_commit_ref
│   │   └── sink.py            #     publish_ready_articles (sedimentation timer)
│   ├── reviews/
│   │   ├── __init__.py        #     Review read wrappers
│   │   ├── submit.py          #     submit_review (git-first: write → commit → DB cache)
│   │   ├── invite.py          #     invite_reviewer, accept_invitation, decline_invitation
│   │   └── thread.py          #     submit_reply, thread management
│   └── reconcile/
│       ├── __init__.py        #     Integrity verification facade
│       ├── mirror.py          #     Git→DB mirror (read canonical state from git, write to DB)
│       └── score.py           #     Score reconciliation from git review data

├── compute/                   # Pure compute — zero storage/IO dependencies
│   ├── scoring.py             #   aggregate_review_scores (weighted average)
│   ├── sedimentation.py       #   is_ready_to_publish, apply_no_review_penalty
│   ├── reputation.py          #   compute_reputation, blend_reputation
│   ├── bfs.py                 #   Graph traversal (social graph discovery)
│   ├── monotonic.py           #   k-exponential monotonic search (ancestor probe)
│   └── state.py               #   Frozen dataclass serialization

├── storage/                   # Local persistence
│   ├── locks.py               #   File-based lock for concurrent git writes
│   ├── peers.py               #   Known peers registry (JSON file)
│   ├── git/                   #   Git backend — articles as independent git repos
│   │   ├── __init__.py        #     Re-exports all git operations
│   │   ├── ops.py             #     init, commit, status, diff, clone
│   │   ├── read.py            #     read_source, get_head, history, authors
│   │   ├── bundle.py          #     create_bundle, ingest_bundle
│   │   ├── merge.py           #     merge_git_repos (fork → mainline)
│   │   ├── ancestor.py        #     is_ancestor check
│   │   ├── archive.py         #     tar.gz pack/unpack (first-time upload)
│   │   ├── trailers.py        #     Commit trailer parsing (Closes:, Pubkey:)
│   │   └── guards.py          #     require_article_repo guard
│   └── db/                    #   SQLite — metadata cache (only layer importing sqlalchemy)
│       ├── engine.py          #     SQLAlchemy engine, JSONList/JSONDict types, migrations
│       ├── models.py          #     ORM: Article, User, Review, Follow, MergeProposal, …
│       ├── session_utils.py   #     Transaction lifecycle
│       ├── guards.py          #     DB-level guards
│       ├── state.py           #     DB state extraction for workflow snapshots
│       ├── crawler.py         #     P2P social graph crawler
│       ├── ingest.py          #     Data ingestion from peer sync
│       ├── _validators.py     #     Input validation
│       ├── crud_article.py    #     Article CRUD + publish_consents
│       ├── crud_user.py       #     User, Follow, anonymous names
│       ├── crud_review.py     #     Review score cache
│       ├── crud_maintainer.py #     Maintainer membership
│       ├── crud_merge.py      #     MergeProposal CRUD
│       ├── crud_citation.py   #     Citation edge CRUD
│       ├── crud_bookmark.py   #     Bookmark CRUD
│       ├── crud_share.py      #     Share CRUD
│       ├── crud_alias.py      #     Alias CRUD
│       └── crud_notification.py # Notification CRUD

├── transport/                 # P2P protocol — abstract HTTP callbacks
│   ├── __init__.py            #   Transport dataclass (bundle of fetch_*/push_* callbacks)
│   ├── auth.py                #   Ed25519 auth header signing/verification
│   ├── guards.py              #   Transport-level guards
│   └── http/                  #   HTTP implementation — ONLY layer importing httpx
│       ├── __init__.py        #     Re-exports
│       ├── _core.py           #     Shared: client pool, signed get/post
│       ├── articles.py        #     Article sync: head, bundle, repo, source, search
│       ├── social.py          #     Social graph: follow, share, peers, school
│       ├── factory.py         #     Transport factory (build from config)
│       └── health.py          #     Health check + clock skew

├── server/                    # HTTP server — Starlette; imports core/, never transport/http/
│   ├── app.py                 #   create_app() — Starlette app factory
│   ├── shared.py              #   Shared route utilities
│   ├── middleware/
│   │   ├── __init__.py        #     Re-exports
│   │   ├── auth.py            #     Auth middleware (PEERPEDIA_SKIP_AUTH bypass)
│   │   ├── db.py              #     DB session middleware
│   │   ├── logging.py         #     Request audit logging
│   │   └── ratelimit.py       #     Rate limiter
│   └── routes/
│       ├── __init__.py        #     ALL_ROUTES aggregation
│       ├── articles.py        #     REST routes: head, bundle, sync, ancestor, repo, source, search
│       ├── peers.py           #     Peer registration + discovery
│       └── users.py           #     User profile, social graph, key rotation

├── repl/                      # Interactive REPL — pure UI, only imports from cli/
│   ├── __init__.py            #   run() entry point, dashboard, periodic scan
│   ├── state.py               #   Theme defs, session vars, prompt, completions
│   ├── dispatch.py            #   Meta-commands (:help, :user, :theme, …) + dispatch
│   ├── bridge.py              #   CLI execution bridge
│   ├── browse.py              #   Full-screen article/user/review browsers
│   ├── help.py                #   REPL help system
│   ├── meta.py                #   Meta-command handlers
│   └── wizards.py             #   Interactive input wizards

└── cli/                       # Terminal UI — never imports repl/; imports app/ + core/
    ├── __init__.py            #   main() — parse args, dispatch handler
    ├── parser.py              #   Command table + argparse builder
    ├── decorators.py          #   @with_context: DB session + result rendering + auto-sync
    ├── dispatch.py            #   Command dispatch table
    ├── display.py             #   Rich-powered output: panels, tables, diff, stars, display_user
    ├── info.py                #   _out() / _render_result() / _render_error()
    ├── session.py             #   Session read/write
    ├── bundle_utils.py        #   Auto-sync helpers
    ├── schema_build.py        #   JSON Schema builder
    └── cmds/
        ├── account.py         #     register, login, recover, whoami, bootstrap, search
        ├── article.py         #     create, show, list, edit, publish, delete, scan, diff
        ├── fork.py            #     fork, merge propose/accept/withdraw
        ├── help.py            #     Inline help pages
        ├── maintainers.py     #     add, remove, list, consent, revoke
        ├── mother.py          #     Interactive user guide
        ├── notifications.py   #     list, read
        ├── reviews.py         #     submit, list, reply, invite, accept, decline, rate
        ├── schema.py          #     Database schema inspection
        ├── server.py          #     server start
        ├── social.py          #     follow, unfollow, following, followers, school, bookmark, alias, share
        └── sync.py            #     sync status, push, pull, discover
```

## Module Reference

### `config/` — Application configuration

**`config/paths.py`**
- What it does: Centralised filesystem path resolution, all overridable via `PEERPEDIA_HOME` env var (default `~/.peerpedia`).
- Key exports: `DATA_ROOT`, `DB_PATH`, `DB_URL`, `ARTICLES_DIR`, `SESSION_FILE`, `REPL_HISTORY_FILE`, `PENDING_OPS_FILE`, `BLOBS_DIR`.
- Depends on: stdlib only.
- Used by: Every module that needs to read/write files — CLI, git backend, DB engine, bundle.

**`config/git.py`**
- What it does: Git repo structure constants and SSH signing/verification environment builders.
- Key functions: `make_article_gitignore()`, `ssh_sign_env(allowed_signers, signing_key)`, `ssh_verify_env(allowed_signers)`.
- Key exports: `ARTICLE_REPO_TRACKED_PATTERNS` — the only files allowed in an article repo (`.gitignore`, `article.md`, `article.typ`, `reviews/*`, `compiled/*`).
- Depends on: stdlib only.
- Used by: `storage/git_backend.py` (commit/verify), any module calling `git commit -S` or `git verify-commit`.

**`config/params.py`**
- What it does: Single source of truth for all tunable system parameters.
- Key classes: `SinkParams` (sedimentation timing), `ScoreParams` (weights, penalties), `ReputationParams` (fold threshold), `CommentParams` (length limits), `DiscoveryParams` (seed peers, max peers), `Params` (aggregate). Global instance: `params`.
- Key functions: `make_peerpedia_email(local_part)`.
- Depends on: stdlib only.
- Used by: `workflow/`, `commands/`, `transport/`.

### `types/` — Domain type definitions

**`types/scores.py`**
- What it does: Five-dimension review scores and reputation scores as frozen dataclasses.
- Key classes: `FiveDimScores` (average, weighted_average, to_result), `ReputationScores` (average, to_result).
- Key exports: `SCORE_DIMENSIONS` — tuple of the 5 dimension names; `SCORE_FORMAT_EXAMPLE`.
- Depends on: stdlib only.
- Used by: `workflow/`, `commands/`, `policies/`.

**`types/status.py`**
- What it does: Article status constants and status-tag parsing.
- Key exports: `VALID_ARTICLE_STATUSES` — the set of legal status strings (draft, sedimentation, published, rejected); `parse_status_tag(message, author_email)` — single canonical parser for ``[status]`` markers in platform commit messages.
- Depends on: `peerpedia_core.config.params.PLATFORM_EMAIL`.
- Used by: `storage/git_backend.py`, `commands/bundle.py`, `commands/integrity.py`, `policies/articles.py`.

### Root modules

**`__main__.py`**
- What it does: Top-level entry point router — the ONLY module that imports both `cli` and `repl`. When no subcommand is given, launches the REPL; otherwise delegates to `cli.main()`.
- Key function: `main()`.
- Depends on: `peerpedia_core.cli`, `peerpedia_core.repl` (lazy — prompt_toolkit is heavy).
- Used by: Package entry point (console_scripts: `peerpedia = "peerpedia_core.__main__:main"`).

**`exceptions.py`**
- What it does: Semantic exception hierarchy for the entire application.
- Key classes: `PeerpediaError` (base), `NotFoundError`, `NotAuthorizedError`, `ConflictError`, `MergeConflictError` (shared by `storage/git_backend` and `bundle/git_bundle`), `BadRequestError`, `SignatureVerificationError`, `TransportError`, `ProtocolError`.
- Depends on: stdlib only.
- Used by: Every layer — raised in `commands/`, `storage/`, `transport/`, caught in `cli/`.

**`crypto.py`**
- What it does: Ed25519 key derivation (scrypt → seed → key pair), signing, verification, SSH-formatted key serialization.
- Key functions: `derive_key_pair(password, salt_hex)`, `derive_pubkey_hex(password, salt_hex)`, `pubkey_hex_to_ssh_line(pubkey_hex)`, `serialize_private_key_pem(key_bytes)`, `sign_detached(key_bytes, message)`, `verify_signature(pubkey_bytes, message, signature)`, `new_salt()`, `temp_signing_key(key_bytes)` (context manager).
- Depends on: `cryptography` library, stdlib.
- Used by: `commands/` (signing commits), `transport/auth.py` (HTTP auth), `cli/handlers/account.py` (registration/login).

**`frontmatter.py`**
- What it does: Parse and build YAML frontmatter for article files.
- Key functions: `parse_frontmatter(text)`, `make_frontmatter(fields)`, `make_article_frontmatter(title, uid, ...)`, `strip_frontmatter(text)`.
- Depends on: stdlib only.
- Used by: `commands/articles/create.py`, `commands/articles/update.py`, `compiler.py`.

**`names.py`**
- What it does: Anonymous reviewer display names (deterministic or random), no I/O.
- Key functions: `generate_anonymous_name()` (random), `derive_anonymous_name(seed)` (SHA-256 → index into 100×100 adjective+noun grid).
- Depends on: stdlib only.
- Used by: `commands/reviews.py`.

**`compiler.py`**
- What it does: Compile Markdown or Typst source to HTML, PDF, SVG, or PNG.
- Key functions: `compile_article(source, format, output)`, `detect_format(source)`.
- Key classes: `CompileResult`, `MarkdownBackend`, `TypstBackend`.
- Depends on: `peerpedia_core.frontmatter.strip_frontmatter`.
- Used by: `cli/handlers/compile_.py`.

### `policies/articles.py`

- What it does: All permission/authorization checks for article operations.
- Key functions: `visible_statuses_for_user()`, `assert_not_folded()`, `assert_can_read_article()`, `assert_can_edit_article()`, `assert_can_delete_article()`, `assert_can_publish_article()`, `assert_can_submit_review()`, `assert_can_reply_to_review()`, `assert_can_sync_article()`, `assert_can_fork_article()`, `assert_can_accept_merge()`, `validate_self_review_scores()`, `assert_article_has_score()`.
- Key exports: `PUBLIC_READABLE_STATUSES`, `FORKABLE_STATUSES`.
- Depends on: `peerpedia_core.exceptions`, `peerpedia_core.storage.db.models`, `peerpedia_core.types.scores`.
- Used by: `commands/` — every article mutating operation calls these assertions first.

### `storage/` — Local persistence

**`storage/git_backend.py`**
- What it does: Layer 0 git storage — every article is an independent git repo under `~/.peerpedia/articles/<id>/`. Pure local git, no DB dependency.
- Key functions: `init_article_repo(repo_path)` — create repo with `.gitignore` + initial commit; `commit_article(repo_path, message, author_name, email, signing_key, pubkey_hex)` — stage all, commit with optional SSH signature; `commit_status_marker(repo_path, status)` — platform [status] commit; `get_commit_history(repo_path)`, `get_commit_authors(repo_path)`, `get_diff_between(repo_path, a, b)`, `merge_git_repos(target, fork)`, `list_review_dirs(repo_path)`, `read_review_scores(repo_path)`, `verify_commit_signature(repo_path, commit_hash)`, `read_article_source(repo_path)`.
- Key exports: `MergeConflictError`.
- Depends on: `git` (GitPython), `peerpedia_core.config.git`, `peerpedia_core.config.paths`, `peerpedia_core.config.params.PLATFORM_EMAIL`, `peerpedia_core.types.status.VALID_ARTICLE_STATUSES`, `peerpedia_core.exceptions.ConflictError`.
- Used by: `commands/` (create, update, publish, fork, rollback, delete, merge), `bundle/` (sync), `commands/bundle.py` (sync reviews).

**`storage/locks.py`**
- What it does: File-based lock to serialize concurrent git writes to a single article repo.
- Key functions: `get_article_lock(article_id)` — returns a context manager acquiring/releasing a lock file.
- Key class: `_TrackedLock`.
- Depends on: stdlib only.
- Used by: `commands/reviews.py`.

**`storage/db/engine.py`**
- What it does: SQLAlchemy engine setup, DB initialization, schema migration, custom column types.
- Key functions: `get_engine()`, `init_db()`, `migrate_db()`, `get_session()`.
- Key exports: `Base` (declarative base), `JSONList`, `JSONDict` (custom SQLAlchemy types).
- Depends on: `sqlalchemy`.
- Used by: `storage/db/models.py`, `storage/db/session_utils.py`, `cli/`.

**`storage/db/models.py`**
- What it does: SQLAlchemy ORM models for all entities.
- Key classes: `Article`, `Review`, `ArticleAuthor`, `ScriptMaintainer`, `User`, `Follow`, `Alias`, `Share`, `Bookmark`, `Notification`, `MergeProposal`, `Citation`.
- Depends on: `peerpedia_core.storage.db.engine.Base`.
- Used by: All `crud_*.py` files, `policies/articles.py`, `commands/`.

**`storage/db/session_utils.py`**
- What it does: Transaction lifecycle management.
- Key functions: `db_session_scope()` — context manager that creates a session, commits on success, rolls back on exception.
- Depends on: `peerpedia_core.storage.db.engine`.
- Used by: `commands/__init__.py` (re-exported as `db_session`), `cli/helpers.py`.

**`storage/db/crud_article.py`**
- What it does: Article CRUD plus publish consents, sink tracking, fork counting.
- Key functions: `create_article()`, `get_article()`, `list_articles()`, `update_article_status()`, `update_article_score()`, `extend_sink()`, `add_publish_consent()`, `clear_publish_consents()`, `update_witnessed_at()`, `increment_fork_count()`, `delete_article()`, `set_article_authors()`.
- Depends on: `peerpedia_core.storage.db.models`, `peerpedia_core.exceptions`.
- Used by: `commands/` (all article operations, workflow, bundle, reviews, maintainers).

**`storage/db/crud_user.py`**
- What it does: User lifecycle, following graph, reputation storage.
- Key functions: `create_user()`, `create_user_stub()`, `get_user()`, `get_user_by_name()`, `search_users()`, `update_user_public_key()`, `update_user_salt()`, `update_user_reputation()`, `follow_user()`, `unfollow_user()`, `is_following()`, `get_followers()`, `get_following()`, `get_top_users_by_followers()`, `soft_delete_user()`.
- Depends on: `peerpedia_core.storage.db.models`, `peerpedia_core.exceptions`.
- Used by: `commands/users.py`, `commands/discover.py`, `commands/workflow.py`, `commands/maintainers.py`, `crud_alias.py`.

**`storage/db/crud_review.py`**
- What it does: Review score cache (DB mirrors git; git is source of truth).
- Key functions: `upsert_review(db, article_id, commit_hash, reviewer_id, scores)`, `get_reviews_for_article(db, article_id)`, `get_review(db, article_id, reviewer_id)`.
- Depends on: `peerpedia_core.storage.db.models`.
- Used by: `commands/reviews.py`, `commands/workflow.py`, `commands/bundle.py`.

**`storage/db/crud_maintainer.py`**
- What it does: Script maintainer membership (who can publish, edit, accept merges).
- Key functions: `add_maintainer()`, `remove_maintainer()`, `get_maintainer_ids()`, `is_maintainer()`.
- Depends on: `peerpedia_core.storage.db.models`.
- Used by: `commands/maintainers.py`, `commands/articles/publish.py`, `commands/articles/rollback.py`, `commands/reviews.py`.

**`storage/db/crud_merge.py`**
- What it does: Merge proposal lifecycle.
- Key functions: `create_merge_proposal()`, `get_merge_proposal()`, `get_merge_proposals_for_article()`, `accept_merge_proposal()`, `reject_merge_proposal()`, `withdraw_merge_proposal()`.
- Depends on: `peerpedia_core.storage.db.models`.
- Used by: `commands/merge.py`.

**`storage/db/crud_citation.py`**
- What it does: Citation edge CRUD (which articles cite which).
- Key functions: `create_or_update_citation()`, `get_citation()`, `get_citations()`, `get_cites()`, `get_cited_by()`.
- Depends on: `peerpedia_core.storage.db.models`.
- Used by: `commands/` (citation operations).

**`storage/db/crud_bookmark.py`**
- What it does: Personal bookmark CRUD (private to user).
- Key functions: `add_bookmark()`, `remove_bookmark()`, `is_bookmarked()`, `get_bookmarks_for_user()`.
- Depends on: `peerpedia_core.storage.db.models`.
- Used by: `commands/bookmarks.py`, `commands/discover.py`.

**`storage/db/crud_share.py`**
- What it does: Article sharing CRUD (social signal).
- Key functions: `add_share()`, `remove_share()`, `is_shared()`, `get_shares_for_user()`, `get_shares_by_followed()`.
- Depends on: `peerpedia_core.storage.db.models`.
- Used by: `commands/shares.py`, `commands/discover.py`.

**`storage/db/crud_alias.py`**
- What it does: Local nickname CRUD (user→alias mapping, private to caller).
- Key functions: `set_alias()`, `remove_alias()`, `get_alias_for()`, `list_aliases()`, `resolve_username_or_alias()`.
- Depends on: `peerpedia_core.storage.db.models`, `peerpedia_core.storage.db.crud_user.is_following`, `peerpedia_core.exceptions`.
- Used by: `commands/` (alias operations).

**`storage/db/crud_notification.py`**
- What it does: In-app notification CRUD.
- Key functions: `create_notification()`, `get_notifications()`, `mark_read()`, `count_unread_notifications()`.
- Depends on: `peerpedia_core.storage.db.models`.
- Used by: `commands/notifications.py`.

### `commands/` — Business logic orchestration

**`commands/__init__.py`**
- What it does: Facade that re-exports all public functions from submodules plus `db_session()` and `health_check()`.
- Key re-exports: All functions from `articles/`, `bookmarks`, `maintainers`, `merge`, `reviews`, `shares`, `bundle`, `users`, `workflow`, `views`, `discover`, `notifications`.
- Depends on: All `commands/` submodules, `peerpedia_core.storage.db`, `peerpedia_core.frontmatter`.
- Used by: `transport/http_server.py`, `transport/routes/`, `cli/`.

**`commands/users.py`**
- What it does: User lifecycle orchestration (wrap `crud_user` with notifications).
- Key functions: `create_user()`, `get_user()`, `follow_user()` (+ creates notification), `unfollow_user()`, `get_followers()`, `get_following()`, `search_users()`, `soft_delete_user()`.
- Depends on: `peerpedia_core.storage.db.crud_user`, `peerpedia_core.commands.notifications`.
- Used by: `transport/routes/users.py`, `cli/handlers/account.py`.

**`commands/notifications.py`**
- What it does: Notification CRUD with batch creation for publishing.
- Key functions: `create_notification()`, `get_notifications()`, `mark_read()`, `count_unread_notifications()`, `merge_notifications()`, `create_notifications_batch()`.
- Depends on: `peerpedia_core.storage.db`, `peerpedia_core.storage.db.crud_notification`.
- Used by: `commands/users.py`, `commands/reviews.py`, `commands/merge.py`, `commands/articles/publish.py`, `commands/discover.py`.

**`commands/discover.py`**
- What it does: Merge peer data into local DB (called after social fetch).
- Key functions: `merge_users()`, `merge_follows()`, `merge_followers()`, `merge_article_meta()`, `merge_bookmarks()`, `merge_script_maintainers()`, `merge_shares()`, `merge_notifications()`.
- Depends on: All `peerpedia_core.storage.db.crud_*` modules.
- Used by: `social/exchange.py`.

**`commands/views.py`**
- What it does: Build response-ready dicts for REST API and CLI.
- Key functions: `get_article_view()`, `list_article_views()`, `get_user_view()`, `get_following_views()`, `get_follower_views()`, `list_user_article_views()`.
- Depends on: `peerpedia_core.storage.db.crud_article`, `peerpedia_core.storage.db.crud_user`.
- Used by: `transport/routes/articles.py`, `cli/display.py`.

**`commands/integrity.py`**
- What it does: Verify article integrity — commit signatures match DB authors, git state matches DB metadata.
- Key functions: `assert_article_integrity(db, article_id)` — checks every commit's SSH signature against the author's stored pubkey, verifies status markers, validates author trail.
- Depends on: `peerpedia_core.crypto`, `peerpedia_core.storage.git_backend`, `peerpedia_core.storage.db.crud_article`.
- Used by: `commands/articles/update.py`, `commands/articles/publish.py`, `commands/articles/fork.py`, `commands/articles/rollback.py`, `commands/articles/delete.py`, `commands/bundle.py`.

**`commands/workflow.py`**
- What it does: Background compute — publish ready articles, recompute scores and reputations.
- Key functions: `publish_ready_articles(db)` — scan all sedimentation articles, check `is_ready_to_publish`, transition to published; `recompute_article_score(db, article_id)` — aggregate reviews + apply no-review penalty; `recompute_author_reputation(db, author_id)` — blend article scores into author reputation; `recompute_all_reputations(db)`, `extract_state(db)`.
- Depends on: `peerpedia_core.workflow.*` (pure compute), `peerpedia_core.storage.db.crud_*`, `peerpedia_core.storage.git_backend`.
- Used by: `commands/reviews.py` (after review submission), `commands/articles/publish.py`, `commands/bundle.py`, CLI REPL timer.

**`commands/bundle.py`**
- What it does: After git bundle sync, reconcile the DB cache with updated git state.
- Key functions: `apply_sync_bundle(db, article_id)` — merge FETCH_HEAD, sync reviews from worktree, recompute scores; `sync_reviews_from_worktree(db, article_id)` — read all `scores.json` from git worktree and upsert into DB Review table; `sync_status_from_git(db, article_id)`.
- Depends on: `peerpedia_core.storage.git_backend`, all `crud_*`, `peerpedia_core.commands.workflow`, `peerpedia_core.commands.integrity`.
- Used by: `bundle/client.py`, `bundle/server.py`.

**`commands/reviews.py`**
- What it does: Review lifecycle — submit, reply, invite, rate helpfulness.
- Key functions: `submit_review(db, article_id, reviewer_id, scores, comment, signing_key_bytes, pubkey_hex)` — git-first: write review to git, then upsert DB cache, then recompute score + reputation; `submit_reply(db, article_id, reviewer_id, reply_to_id, comment)`, `invite_reviewer(db, article_id, inviter_id, invitee_id)`, `rate_review_helpfulness(db, article_id, reviewer_id, rater_id, helpful)`.
- Depends on: `peerpedia_core.policies.articles`, `peerpedia_core.names`, `peerpedia_core.crypto`, `peerpedia_core.storage.git_backend`, `peerpedia_core.storage.locks`, `peerpedia_core.commands.workflow`.
- Used by: `cli/handlers/reviews.py`.

**`commands/merge.py`**
- What it does: Merge proposal lifecycle (fork → proposal → vote → merge).
- Key functions: `create_merge_proposal(db, article_id, proposer_id, source_repo_path)`, `accept_merge(db, article_id, maintainer_id, proposal_id)`, `withdraw_merge_proposal(db, proposal_id, caller_id)`.
- Depends on: `peerpedia_core.policies.articles`, `peerpedia_core.storage.db.crud_merge`, `peerpedia_core.storage.git_backend`, `peerpedia_core.commands.notifications`.
- Used by: `cli/handlers/social.py`.

**`commands/maintainers.py`**
- What it does: Maintainer membership management + publish consent.
- Key functions: `add_maintainer_to_article()`, `remove_maintainer_from_article()`, `list_maintainers()`, `consent_to_publish()`, `revoke_publish_consent()`.
- Depends on: `peerpedia_core.storage.db.crud_maintainer`, `peerpedia_core.storage.db.crud_article`, `peerpedia_core.storage.db.crud_user`.
- Used by: `cli/handlers/maintainers.py`.

**`commands/bookmarks.py`**
- What it does: Personal bookmark operations.
- Key functions: `add_bookmark()`, `remove_bookmark()`, `get_bookmarks_for_user()`.
- Depends on: `peerpedia_core.storage.db.crud_bookmark`.
- Used by: `cli/handlers/social.py`.

**`commands/shares.py`**
- What it does: Article sharing operations.
- Key functions: `add_share()`, `remove_share()`, `get_shares_for_user()`, `get_feed_shares()`.
- Depends on: `peerpedia_core.storage.db.crud_share`.
- Used by: `cli/handlers/social.py`.

**`commands/trailers.py`**
- What it does: Parse commit message trailers for review/merge close semantics.
- Key functions: `parse_closes_trailer(commit_message)`, `validate_closes_target(db, article_id, target_id)`, `list_review_threads(repo_path)`.
- Depends on: `peerpedia_core.storage.git_backend.DEFAULT_ARTICLES_DIR`.
- Used by: `commands/articles/update.py`.

**`commands/articles/__init__.py`**
- What it does: Read wrappers + re-exports all article submodule functions.
- Key functions: `get_article()`, `list_articles()`, `count_articles()`, `get_all_article_ids()`, `get_author_ids()`.
- Re-exports: `create_article_with_content`, `update_article_content`, `publish_article`, `fork_article`, `rollback_article`, `delete_article`, `diff_article`, `rebuild_article_authors`.
- Depends on: All `commands/articles/*.py`, `peerpedia_core.storage.db.crud_article`.

**`commands/articles/_helpers.py`**
- What it does: Shared helpers for article operations — user/article/repo resolution, sink reset, author rebuild, maintainer check.
- Key functions: `require_user()`, `require_article()`, `require_article_repo()`, `_reset_sink()`, `rebuild_article_authors()`, `_assert_caller_is_maintainer()`.
- Depends on: `peerpedia_core.storage.db.crud_article`, `peerpedia_core.storage.db.crud_user`, `peerpedia_core.storage.git_backend`.
- Used by: All `commands/articles/*.py`, `commands/reviews.py`, `commands/merge.py`.

**`commands/articles/create.py`**
- What it does: Create a new article — write git repo, DB row, add creator as first maintainer.
- Key function: `create_article_with_content(db, author_id, title, content, format, signing_key_bytes)`.
- Depends on: `peerpedia_core.frontmatter`, `peerpedia_core.storage.git_backend`, `peerpedia_core.storage.db.crud_article`, `peerpedia_core.storage.db.crud_maintainer`, `peerpedia_core.crypto`.
- Used by: `cli/handlers/articles.py`.

**`commands/articles/update.py`**
- What it does: Update article content — write new commit, clear publish consents, verify integrity.
- Key function: `update_article_content(db, article_id, caller_id, content, format, commit_message, signing_key_bytes)`.
- Depends on: `peerpedia_core.frontmatter`, `peerpedia_core.policies.articles`, `peerpedia_core.storage.git_backend`, `peerpedia_core.crypto`, `peerpedia_core.commands.integrity`, `peerpedia_core.commands.trailers`.
- Used by: `cli/handlers/articles.py`.

**`commands/articles/publish.py`**
- What it does: Transition from sedimentation to published — check consents, write final commit, notify followers, recompute score.
- Key function: `publish_article(db, article_id, caller_id, signing_key_bytes)`.
- Depends on: `peerpedia_core.policies.articles`, `peerpedia_core.storage.db.crud_article`, `peerpedia_core.storage.db.crud_maintainer`, `peerpedia_core.storage.db.crud_review`, `peerpedia_core.storage.db.crud_user`, `peerpedia_core.storage.git_backend`, `peerpedia_core.commands.workflow`, `peerpedia_core.commands.notifications`.
- Used by: `cli/handlers/articles.py`.

**`commands/articles/fork.py`**
- What it does: Fork an article — copy repo, create new DB record, set sink, add forker as maintainer.
- Key function: `fork_article(db, caller_id, source_article_id, new_title, signing_key_bytes)`.
- Depends on: `peerpedia_core.policies.articles`, `peerpedia_core.storage.git_backend`, `peerpedia_core.storage.db.crud_article`, `peerpedia_core.storage.db.crud_maintainer`, `peerpedia_core.commands.integrity`.
- Used by: `cli/handlers/social.py`.

**`commands/articles/rollback.py`**
- What it does: Roll back to a previous commit — write revert commit, clear consents, recompute score.
- Key function: `rollback_article(db, article_id, caller_id, target_commit, signing_key_bytes)`.
- Depends on: `peerpedia_core.policies.articles`, `peerpedia_core.storage.git_backend`, `peerpedia_core.storage.db.crud_maintainer`, `peerpedia_core.commands.workflow`, `peerpedia_core.crypto`.
- Used by: `cli/handlers/articles.py`.

**`commands/articles/delete.py`**
- What it does: Soft-delete article — set status, optionally delete git repo.
- Key function: `delete_article(db, article_id, caller_id)`.
- Depends on: `peerpedia_core.policies.articles`, `peerpedia_core.storage.db.crud_article`, `peerpedia_core.storage.db.crud_maintainer`, `peerpedia_core.storage.git_backend`, `peerpedia_core.commands.integrity`.
- Used by: `cli/handlers/articles.py`.

**`commands/articles/diff.py`**
- What it does: Diff two commits of an article.
- Key functions: `diff_article(db, article_id, commit_a, commit_b)`, `resolve_commit_ref(repo_path, ref)`.
- Depends on: `peerpedia_core.storage.git_backend`.
- Used by: `cli/handlers/articles.py`.

### `workflow/` — Pure compute (no I/O)

**`workflow/scoring.py`**
- What it does: Aggregate review scores into a weighted average per dimension.
- Key functions: `aggregate_review_scores(reviews, author_ids, self_review_weight, community_weight)` — combines self-reviews and community reviews with separate weights.
- Depends on: `peerpedia_core.config.params.params`, `peerpedia_core.types.scores.SCORE_DIMENSIONS`.
- Used by: `commands/workflow.py`.

**`workflow/sedimentation.py`**
- What it does: Sedimentation pool timing — determine if an article is ready to leave the pool.
- Key functions: `is_ready_to_publish(sink_eta)` — compare sink ETA to current UTC time; `apply_no_review_penalty(scores)` — subtract configured penalty when no reviews received. Raises `TypeError` on None (fail fast).
- Depends on: `peerpedia_core.config.params.params`.
- Used by: `commands/workflow.py`.

**`workflow/reputation.py`**
- What it does: Compute and blend author reputations from article scores.
- Key functions: `compute_reputation(db_snapshot)` — calculate reputation from article + review history; `blend_reputation(base, incoming, weight)` — merge existing reputation with new data; `get_reviewer_weight(reputation)` — weight a reviewer's scores by their reputation.
- Depends on: `peerpedia_core.config.params.params`, `peerpedia_core.types.scores`, `peerpedia_core.workflow.state.ReputationState`.
- Used by: `commands/workflow.py`.

**`workflow/state.py`**
- What it does: Frozen dataclass snapshots for passing state between workflow steps.
- Key classes: `ArticleSnapshot`, `ReviewSnapshot`, `UserSnapshot`, `FollowSnapshot`, `ShareSnapshot`, `MergeProposalSnapshot`, `ReputationState`.
- Depends on: stdlib only (`dataclasses`).
- Used by: `commands/workflow.py`.

### `bundle/` — Git bundle protocol

**`bundle/client.py`**
- What it does: Client-side sync orchestration — push/pull article repos to/from a remote peer.
- Key functions: `sync_article(db, server_url, article_id, signing_key_bytes, pubkey_hex)` — orchestrates the full sync protocol; `find_merge_base(server, article_id, local_commits)`, `pull_incremental(server, article_id, local_head)`, `pull_new_article(server, article_id)`, `push_incremental(server, article_id, server_head, repo_path)`, `upload_article(server, article_id, repo_path)`.
- Depends on: `peerpedia_core.bundle.git_bundle` (including `ingest_article`), `peerpedia_core.commands.apply_sync_bundle`, `peerpedia_core.transport.*`, `peerpedia_core.transport.health.check_clock_skew`. Does NOT import from `bundle.server` — client and server communicate via HTTP, not Python import.
- Used by: `cli/handlers/bundle.py`.

**`bundle/git_bundle.py`**
- What it does: Low-level git bundle create/apply and common ancestor discovery.
- Key functions: `init_repo(path)` — ensure a valid git repo exists; `create_bundle(repo_path, since_hash)` — create git bundle as bytes; `ingest_bundle(repo_path, bundle_bytes)` — apply bundle (ff-only); `find_common_ancestor(probe_fn, local_commits)` — wraps `monotonic.search_monotonic_boundary`; `pack_article_repo(repo_path)` — tar.gz the whole repo; `ingest_article_repo(repo_path, tar_bytes)` — unpack tar.gz.
- Key exports: `MergeConflictError`.
- Depends on: `git`, `peerpedia_core.bundle.monotonic`, `peerpedia_core.exceptions.ConflictError`.
- Used by: `bundle/client.py`, `bundle/server.py`, `commands/bundle.py`.

**`bundle/monotonic.py`**
- What it does: Exponential + binary search over a monotonic False→True sequence. Used to find the common ancestor with minimum round-trips.
- Key function: `search_monotonic_boundary(probe_at, max_index, k=5)` — Phase 1: k-exponential gallop (1, k, k^2, ...) to bracket the boundary; Phase 2: binary refinement in (last_no, first_yes]. Returns the first True index or None.
- Depends on: stdlib only. Pure abstract algorithm.
- Used by: `bundle/git_bundle.py`.

**`bundle/pending.py`**
- What it does: Offline operation queue — persist sync operations when offline, replay when online.
- Key functions: `add(operation)`, `list_all()`, `count()`, `remove(op_id)`, `clear()`.
- Depends on: `peerpedia_core.config.paths.PENDING_OPS_FILE`.
- Used by: `cli/handlers/articles.py`, `cli/handlers/bundle.py`.

**`bundle/server.py`**
- What it does: Server-side bundle handlers — receive bundles, serve bundles, check ancestors.
- Key functions: `get_article_head(article_id)`, `get_article_bundle(article_id, since)`, `check_article_ancestor(article_id, commit_hash)`, `apply_sync(article_id, bundle_bytes)`, `ingest_first_article(tar_bytes)` — unpack tar.gz and init repo; `read_article_source_content(article_id)`, `pack_article_repo_bundle(article_id)`.
- Depends on: `peerpedia_core.storage.git_backend`, `peerpedia_core.bundle.git_bundle`, `peerpedia_core.commands.apply_sync_bundle`, `peerpedia_core.storage.db`.
- Used by: `transport/routes/articles.py`.

### `social/` — P2P social graph exchange

**`social/discovery.py`**
- What it does: Peer discovery — maintain known peer list, merge peer records.
- Key functions: `get_known_peers(db)`, `merge_peers(db, peer_list)`.
- Depends on: `peerpedia_core.config.params.params`, `peerpedia_core.transport.fetch_peers`.
- Used by: `cli/handlers/social.py`.

**`social/exchange.py`**
- What it does: Fetch social graph data from a peer server and merge into local DB.
- Key functions: `discover_following(db, server, user_id, **auth)` → `fetch_following` → `merge_follows`; `discover_followers(db, server, user_id, **auth)` → `fetch_followers` → `merge_users` + `merge_followers`; `discover_articles(db, server, user_id, **auth)` → `fetch_user_articles` → `merge_article_meta`; `discover_shares(db, server, user_id, **auth)`, `discover_notifications(db, server, user_id, **auth)`.
- Depends on: `peerpedia_core.transport.*`, `peerpedia_core.commands.*` (merge functions), `peerpedia_core.storage.db`.
- Used by: `cli/handlers/social.py`.

### `transport/` — HTTP layer

**`transport/_http_core.py`**
- What it does: Shared HTTP infrastructure — thread-safe client pool, URL/body helpers, signed `GET`/`POST` wrappers with Ed25519 auth.
- Key functions: `_get_client()` → shared `httpx.Client`; `close_client()`; `_api_url()`; `_signed_get()`; `_signed_post()`.
- Key exports: `_SYNC_TIMEOUT`.
- Depends on: `httpx`, `peerpedia_core.exceptions`, `peerpedia_core.transport.auth`.
- Used by: `transport/http_articles.py`, `transport/http_social.py`.

**`transport/http_articles.py`**
- What it does: Article-level HTTP calls — sync protocol (head, bundle, ancestor probe), repo upload/download, source fetch, search, metadata.
- Key functions: `ancestor_probe()`, `fetch_head()`, `push_bundle()`, `fetch_incremental_bundle()`, `fetch_article_repo()`, `push_article_repo()`, `fetch_article_source()`, `fetch_search()`, `fetch_article_meta()`, `fetch_user_articles()`.
- Depends on: `httpx`, `peerpedia_core.exceptions`, `transport/_http_core.py`.
- Used by: `bundle/client.py`, `cli/bundle_utils.py`.

**`transport/http_social.py`**
- What it does: Social-layer HTTP calls — follow/unfollow, user profiles, school, peers, shares, notifications, key rotation.
- Key functions: `fetch_following()`, `fetch_followers()`, `push_follow()`, `push_unfollow()`, `push_key_rotation()`, `push_share()`, `push_share_remove()`, `fetch_shares()`, `fetch_notifications()`, `fetch_peers()`, `push_peer_registration()`, `fetch_user()`, `fetch_school()`.
- Depends on: `httpx`, `peerpedia_core.exceptions`, `transport/_http_core.py`, `transport/auth.py`.
- Used by: `social/exchange.py`, `social/discovery.py`, `cli/handlers/social.py`.

**`transport/http_client.py`**
- What it does: Facade that re-exports all `fetch_*` / `push_*` functions from `http_articles.py` and `http_social.py`, plus `close_client()` from `_http_core.py`. External code imports from here (or `transport/__init__.py`).
- Depends on: `transport/http_articles`, `transport/http_social`, `transport/_http_core`.
- Used by: `transport/__init__.py`, tests.

**`transport/http_server.py`**
- What it does: Starlette ASGI application — routing, middleware, error handling.
- Key function: `create_app(db_url=None)` — assemble routes from `transport/routes/*`, attach middleware stack (auth, DB session, logging, rate limit), register exception handlers.
- Depends on: `starlette`, `peerpedia_core.commands`, `peerpedia_core.transport.middleware.*`, `peerpedia_core.transport.routes.ALL_ROUTES`.
- Used by: `cli/handlers/server.py`.

**`transport/auth.py`**
- What it does: Ed25519 HTTP auth header signing and verification.
- Key functions: `sign_auth_header(method, path, body, uid, signing_key_bytes)` — derives a bearer token as `Peerpedia <uid>:<ts>:<body_hash>:<sig>`; `verify_auth_header(request, get_user_pubkey)` — checks timestamp (±30s), recomputes body hash, verifies Ed25519 signature. Returns `AuthResult`.
- Depends on: `peerpedia_core.crypto`.
- Used by: `transport/http_client.py`, `transport/middleware/auth.py`.

**`transport/shared.py`**
- What it does: Shared HTTP utility functions for route handlers.
- Key functions: `_validate_id(id, label)`, `_require_field(body, field)`, `_ok_response(data)`, `_parse_pagination(params)`.
- Depends on: `peerpedia_core.exceptions.BadRequestError`.
- Used by: `transport/routes/articles.py`, `transport/routes/users.py`.

**`transport/health.py`**
- What it does: Network health checks — online status, clock skew measurement.
- Key functions: `is_online(server_url, timeout=5)` — GET /health, return bool; `check_clock_skew(server_url)` — compare local time to `Date` header, return skew seconds.
- Depends on: `httpx`, stdlib.
- Used by: `cli/bundle_utils.py`, `transport/__init__.py`.

**`transport/middleware/auth.py`**
- What it does: Starlette middleware that verifies the `Authorization` header on every request. Sets `request.state.user_id` on success. Bypass via `PEERPEDIA_SKIP_AUTH=1` env var (for tests).
- Key class: `AuthMiddleware`.
- Depends on: `peerpedia_core.transport.auth.verify_auth_header`, `peerpedia_core.commands`.
- Used by: `transport/http_server.py`.

**`transport/middleware/db.py`**
- What it does: Middleware that creates a DB session per request and attaches to `request.state.db`. Commits on 2xx, rolls back on error.
- Key classes: `DBSessionMiddleware`, `DbRoute` (route class that auto-injects db session).
- Depends on: `peerpedia_core.commands.db_session`, `peerpedia_core.config.paths.DB_URL`.
- Used by: `transport/http_server.py`.

**`transport/middleware/logging.py`**
- What it does: Structured request logging middleware — method, path, status, duration.
- Key class: `AuditLogMiddleware`.
- Depends on: stdlib (`logging`).
- Used by: `transport/http_server.py`.

**`transport/middleware/ratelimit.py`**
- What it does: In-memory rate limiter per IP (sliding window).
- Key class: `RateLimitMiddleware`.
- Depends on: stdlib.
- Used by: `transport/http_server.py`.

**`transport/routes/articles.py`**
- What it does: REST route handlers for articles — metadata, head, bundle, sync, ancestor probe, history, source, search.
- Key endpoints: `GET /api/v1/articles/{id}` (metadata), `GET /{id}/head` (git HEAD hash), `GET /{id}/bundle?since=` (incremental bundle), `POST /{id}/sync` (apply push bundle), `GET /{id}/ancestor/{hash}` (is-ancestor probe), `POST /api/v1/articles` (first-time upload), `GET /{id}/repo` (full repo download), `GET /{id}/history`, `GET /{id}/source`, `GET /api/v1/search`.
- Key exports: `ROUTES` — list of `starlette.routing.Route`.
- Depends on: `peerpedia_core.bundle.server`, `peerpedia_core.commands`, `peerpedia_core.exceptions`, `peerpedia_core.transport.shared`.
- Used by: `transport/routes/__init__.py`.

**`transport/routes/peers.py`**
- What it does: Peer discovery routes.
- Key function: `add_peer(request)` — POST to register a new peer.
- Key exports: `ROUTES`.
- Depends on: `peerpedia_core.config.params.params`.
- Used by: `transport/routes/__init__.py`.

**`transport/routes/users.py`**
- What it does: User lifecycle routes — profile, social graph, key rotation.
- Key endpoints: `GET /api/v1/users/{id}` (profile), `POST /api/v1/users` (register), `PUT /{id}/key` (key rotation), `PUT /{id}/salt` (salt rotation), `GET /{id}/following`, `GET /{id}/followers`, `POST /{id}/follow`, `POST /{id}/unfollow`, `GET /{id}/articles`, `DELETE /{id}/delete`.
- Key exports: `ROUTES`.
- Depends on: `peerpedia_core.commands`, `peerpedia_core.crypto.load_public_key`, `peerpedia_core.exceptions`, `peerpedia_core.policies.articles.PUBLIC_READABLE_STATUSES`, `peerpedia_core.transport.shared`.
- Used by: `transport/routes/__init__.py`.

### `repl/` — Interactive REPL (pure UI layer)

**`repl/__init__.py`**
- What it does: REPL entry point — `run()` initializes a persistent prompt_toolkit session with startup dashboard, timed article publish scan, and command dispatch loop.
- Key functions: `run()` — start the interactive REPL.
- Depends on: `peerpedia_core.cli` (helpers, display, parser), `peerpedia_core.config`, `peerpedia_core.repl.commands`, `peerpedia_core.repl.state`.
- Used by: `__main__.py` (top-level router).

**`repl/state.py`**
- What it does: Theme definitions (parchment/ember), session variables (`_repl_user`, `_repl_article_id`), prompt builder, completion refresher.
- Key functions: `_prompt_text()` — build the REPL prompt with user badge + article context + notification count; `_refresh_completions()` — rebuild tab-completion word list from DB.
- Key exports: `theme`, `repl_style`, `console`, `_repl_unicode`, `_repl_compact`.
- Depends on: `peerpedia_core.cli.helpers` (all data access), `prompt_toolkit`, `rich`.
- Used by: `repl/__init__.py`, `repl/commands.py`, `repl/browse.py`.

**`repl/commands.py`**
- What it does: Meta-command handlers (`:help`, `:user`, `:article`, `:theme`, `:inbox`, …) and CLI command dispatch — parses user input, injects sticky user/article context, delegates to CLI parser handlers.
- Key functions: `_dispatch(cmd_str, parser)` — parse and execute a single command; `_meta_help()`, `_meta_user(name)`, `_meta_article(ref)`, `_meta_theme(mode)`, `_show_inbox()`.
- Key exports: `_META_COMMANDS`.
- Depends on: `peerpedia_core.cli.helpers` (all data access), `peerpedia_core.cli.parser`, `peerpedia_core.repl.state`, `peerpedia_core.repl.browse` (lazy — prompt_toolkit heavy).
- Used by: `repl/__init__.py`.

**`repl/browse.py`**
- What it does: Full-screen interactive views — article browser, user leaderboard (school), review viewer.
- Key functions: `_browse_articles(db)` — interactive article selector with keyboard shortcuts (p:publish, e:edit, r:review, b:bookmark); `_browse_school(db)` — user leaderboard with follow action; `_browse_reviews(db, article_id)` — review viewer with reply action.
- Depends on: `peerpedia_core.cli.helpers`, `peerpedia_core.cli.display`, `peerpedia_core.repl.state`, `prompt_toolkit`.
- Used by: `repl/commands.py` (lazy — only loaded for browse views).

**`repl/typography.py`**
- What it does: Unicode pseudo-font rendering — maps ASCII to Mathematical Alphanumeric Symbols for six visual roles (bold serif for titles, italic for quotes, script for authors, fraktur for venues, sans-bold for status, monospace for dates/commits).
- Key functions: `title(s)`, `author(s)`, `status(s)`, `date(s)`, `score(val)`, `styled(raw_func)` — wrapper that applies typography only when `_repl_unicode` is enabled.
- Depends on: `peerpedia_core.repl.state` (reads `_repl_unicode` toggle).
- Used by: `repl/commands.py`, `repl/browse.py`.

### `cli/` — Terminal UI

**`cli/__init__.py`**
- What it does: CLI entry point — `main()` parses args and dispatches to a handler. Does NOT know about `repl/` (routing is done by `__main__.py`).
- Key functions: `main()` — parse args, run single command.
- Key exports: `main`, `build_parser`.
- Depends on: `peerpedia_core.cli.parser`, `peerpedia_core.cli.display`, `peerpedia_core.commands`, `peerpedia_core.config.paths`.
- Used by: `__main__.py` (top-level router).

**`cli/parser.py`**
- What it does: Build argparse parser from a command table.
- Key functions: `build_parser()`, `get_cmd_map()`.
- Key exports: `COMMAND_GROUPS`, `TOP_LEVEL`.
- Depends on: `peerpedia_core.cli.handlers.*`, `peerpedia_core.types.scores.SCORE_FORMAT_EXAMPLE`.
- Used by: `cli/__init__.py`.

**`cli/helpers.py`**
- What it does: Shared CLI/REPL utilities — session management, user/article resolution, DB setup, editor integration, JSON output.
- Key functions: `_with_db()` (CLI handler decorator), `_ensure_db()` / `_close_db()` (REPL persistent session), `_get_article_head_hash()`, `_page()`, `_open_file()`, `_ok()`, `_die()`, `_resolve_article_id()`, `_json_out()`, `_find_article_file()`, `_read_session()`, `_write_session()`, `_get_session_user()`, `_get_session_user_id()`, `_resolve_user()`, `_get_session_key()`, `_parse_scores()`, `_prompt_commit_message()`, `_open_editor()`.
- Depends on: `peerpedia_core.cli.display`, `peerpedia_core.commands`, `peerpedia_core.config.paths`, `peerpedia_core.crypto`, `peerpedia_core.exceptions`, `peerpedia_core.storage.db.models`.
- Used by: All `cli/handlers/*.py`, `repl/` (via `cli.helpers`).

**`cli/display.py`**
- What it does: Rich-powered terminal output — panels, tables, badges, diffs.
- Key functions: `_print_panel()`, `_print_table()`, `_status_badge()`, `display_article()`, `display_user()`, `display_diff()`, `_stars()`.
- Key exports: `theme`, `console` (Rich Console).
- Depends on: `peerpedia_core.types.scores.SCORE_DIMENSIONS`.
- Used by: `cli/helpers.py`, all `cli/handlers/*.py`.

**`cli/bundle_utils.py`**
- What it does: Shared sync utilities — server resolution, offline queue replay, auto-push.
- Key functions: `_require_online_server(args)`, `_try_sync(db, article_id, **kwargs)`, `_resolve_server_url(args)`, `_save_default_server(url)`.
- Depends on: `peerpedia_core.bundle`, `peerpedia_core.transport`, `peerpedia_core.social.discover_articles`, `peerpedia_core.cli.helpers`.
- Used by: `cli/handlers/articles.py`, `cli/handlers/bundle.py`, `cli/handlers/social.py`, `cli/handlers/reviews.py`.

**`cli/handlers/__init__.py`**
- What it does: Re-exports all `_cmd_*` functions from handler submodules.
- Depends on: All `cli/handlers/*.py`.
- Used by: `cli/parser.py`.

**`cli/handlers/account.py`**
- Key commands: `_cmd_register` (create user + derive key), `_cmd_login` (authenticate + save session), `_cmd_recover` (re-derive key from password), `_cmd_whoami`, `_cmd_bootstrap` (first-run setup), `_cmd_account_search`, `_cmd_account_delete`.
- Depends on: `peerpedia_core.commands`, `peerpedia_core.crypto`, `peerpedia_core.transport.fetch_user`.

**`cli/handlers/articles.py`**
- Key commands: `_cmd_article_create`, `_cmd_article_show`, `_cmd_article_list`, `_cmd_article_edit`, `_cmd_article_publish`, `_cmd_article_delete`, `_cmd_article_scan` (scan all articles for integrity), `_cmd_article_diff`.
- Depends on: `peerpedia_core.commands`, `peerpedia_core.social.discover_articles`, `peerpedia_core.bundle.pending`, `peerpedia_core.transport.is_online`.

**`cli/handlers/bundle.py`**
- Key commands: `_cmd_sync_status` (show pending/online status), `_cmd_sync_push`, `_cmd_sync_pull`, `_sync_loop`.
- Depends on: `peerpedia_core.bundle`, `peerpedia_core.transport`, `peerpedia_core.commands`.

**`cli/handlers/compile_.py`**
- Key command: `_cmd_compile`.
- Depends on: `peerpedia_core.compiler.compile_article`.

**`cli/handlers/help.py`**
- Key command: `_cmd_meta_help`.
- Depends on: stdlib only.

**`cli/handlers/maintainers.py`**
- Key commands: `_cmd_maintainer_add`, `_cmd_maintainer_remove`, `_cmd_maintainer_list`, `_cmd_maintainer_consent`, `_cmd_maintainer_revoke`.
- Depends on: `peerpedia_core.commands`.

**`cli/handlers/mother.py`**
- Key command: `_cmd_mother` — interactive guide.
- Depends on: `peerpedia_core.cli.display.console`.

**`cli/handlers/notifications.py`**
- Key commands: `_cmd_notifications`, `_cmd_notification_read`.
- Depends on: `peerpedia_core.commands`.

**`cli/handlers/reviews.py`**
- Key commands: `_cmd_review_submit`, `_cmd_review_list`, `_cmd_review_reply`, `_cmd_review_invite`, `_cmd_review_rate`.
- Depends on: `peerpedia_core.commands`, `peerpedia_core.cli.bundle_utils`.

**`cli/handlers/schema.py`**
- Key commands: `_cmd_schema`, `_param_schema`, `_build_command_schema`.
- Depends on: stdlib only.

**`cli/handlers/server.py`**
- Key command: `_cmd_server_start` — launch the Starlette HTTP server.
- Depends on: `peerpedia_core.transport.http_server.create_app`.

**`cli/handlers/social.py`**
- Key commands: `_cmd_fork`, `_cmd_merge_propose`, `_cmd_merge_accept`, `_cmd_merge_withdraw`, `_cmd_bookmark_add/remove/list`, `_cmd_follow/unfollow/following/followers`, `_cmd_alias_set/remove/list`, `_cmd_share_add/list/remove`, `_cmd_school` (sync all from mothership), `_pull_social`, `_push_to_peer`, `_push_social`, `_push_share`.
- Depends on: `peerpedia_core.commands`, `peerpedia_core.social`, `peerpedia_core.transport`, `peerpedia_core.cli.bundle_utils`.

## Layer Rules

```
__main__      ──import──►  cli/
__main__      ──import──►  repl/           (lazy: prompt_toolkit is heavy)
repl/         ──import──►  cli/            (display, parser, dispatch — nothing else)
cli/cmds/     ──import──►  app/            (command facades)
cli/cmds/     ──import──►  core/           (orchestration functions)
app/          ──import──►  core/           (business logic facade)
core/         ──import──►  storage/        (git + db)
core/         ──import──►  transport/      (P2P protocol)
server/       ──import──►  core/           (business logic — never transport/http/)
transport/http/ ─import──►  httpx          (ONLY layer touching HTTP primitives)
storage/db/   ──import──►  sqlalchemy      (ONLY layer touching SQLite)
compute/      ──import──►  (nothing)       (pure compute — zero dependencies)
config/       ──import──►  (nothing)       (foundation)
types/        ──import──►  (nothing)       (foundation)
rules/        ──import──►  storage/db/     (models only, for type hints)
```

- `cli/` never imports from `repl/` — **zero circular dependency**
- `repl/` only imports from `cli/` — no direct `core/` or `storage/` access
- `cli/` imports `core/` + `transport/`, never `storage/` directly
- `app/` imports `core/` + `config/`, never `server/`
- `core/` imports `transport/` (protocol) + `storage/` (git, db). Never imports `server/`
- `server/` imports `core/`. Never imports `transport/http/` directly
- `transport/http/` is the only layer importing `httpx`
- `storage/db/` is the only layer importing `sqlalchemy`
- Foundation (`config/`, `crypto.py`, `time.py`, `exceptions.py`, `types/`, `compute/`) import nothing from other layers
- All import rules enforced by `tests/test_architecture.py`

## Key Design Decisions

### Git-first (write-before-DB)

Reviews are written to git before the DB cache. The git repo is the authoritative record of review scores and article content; the DB Review table is a query cache keyed by `commit_hash`.

```
submit_review:
  1. write_review_to_git() → returns commit_hash    ← git is source of truth
  2. upsert_review(commit_hash=commit_hash)          ← DB cache mirrors git
  3. recompute_article_score()                       ← derived from DB cache
```

This means a DB can be fully rebuilt from git repos (`sync_reviews_from_worktree`). The DB is never the source of truth for content — it's only the source of truth for metadata (status, authorship, following graph, notifications).

### Hash-based sync (k-exponential probing)

P2P article sync uses commit hashes, not branch refs. The protocol finds a common ancestor with minimal round-trips using k-exponential probing:

```
sync_article(server_url, article_id):
  1. fetch_head → server's HEAD hash (404 → first-time upload, send full repo)
  2. List local commits (most recent first)
  3. k-exponential probe: for i in [1, k, k^2, …]:
       GET /ancestor/{commits[i]} → "is this commit in your history?"
     (k=5, so probes happen at indices 1, 5, 25, 125, …)
  4. Binary search in (last_no, first_yes] to find exact merge base
  5. If server ahead:  GET /bundle?since=<merge_base>  → pull_incremental
     If local ahead:   POST /sync with bundle           → push_incremental
  6. If 409 Conflict (diverged): pull first → merge locally → push again
```

`bundle/monotonic.py` implements the abstract search algorithm; `bundle/git_bundle.py:find_common_ancestor` wraps it with git commit indexing.

### Single-mainline (no branches)

Article repositories use `refs/heads/main` only — no feature branches, no topic branches, no merge commits from divergent histories. Collaboration is via fork + merge proposal:

1. Forker runs `fork_article()` → creates a new, independent article repo
2. Forker edits and publishes their fork
3. Forker proposes merge via `create_merge_proposal()`
4. Original maintainers vote with `consent_to_publish()`
5. Maintainer runs `accept_merge()` → calls `merge_git_repos(target, fork)` which pulls the fork's `main` into a FETCH_HEAD and merges

The sync protocol enforces `ff_only=True` on all bundle pushes. Force-pushes are rejected.

### Scrypt key derivation

Password-based Ed25519 key derivation uses the scrypt memory-hard KDF:

```python
_SCRYPT_N = 2**14    # 16384 — CPU/memory cost
_SCRYPT_R = 8        # block size
_SCRYPT_P = 1        # parallelization
_SCRYPT_DKLEN = 32   # 32-byte output → Ed25519 seed

seed = scrypt(password, salt=salt, n=N, r=R, p=P, dklen=32)
(private_key, public_key) = Ed25519.seed_to_keypair(seed)
```

Deterministic: same password + same salt → same key pair every time. Users can recover their key from any device by entering the same password. Each registration generates a new random 16-byte salt (stored in the DB) — registering on a second device produces a different key pair unless the user explicitly copies the salt.

### TOFU auth (Trust On First Use)

When two peers connect for the first time, the server's public key is accepted without prior verification and stored locally. On subsequent connections, the stored key is compared against the presented key:

- **First connection**: store pubkey → trust
- **Subsequent connections**: if pubkey changes → **hard reject** (the user must manually verify and update)
- **Key rotation**: users must explicitly `PUT /users/{id}/key` with an Ed25519 signature from the old key authenticating the new key. The server verifies the transition before updating.

This means key compromise requires manual intervention — there is no automated key rotation that could be exploited by an attacker who briefly compromises the account.

### Local-first

All article operations work offline — git operations (create, edit, fork, rollback) are purely local. The DB is a local SQLite file. Sync is an explicit action:

- **Works offline**: create/edit/publish articles, submit reviews, write reviews to git, read local articles
- **Needs network**: sync with peers, discover social graph, push/pull bundles, register on a remote server
- **Offline queue**: `bundle/pending.py` persists sync operations when offline; `_try_sync` replays them when online

Even `publish_article` works locally — it transitions the status in the local DB and writes a status marker commit. The article only reaches peers when explicitly synced.

### Commit signing (SSH format with Ed25519)

Every non-platform commit is signed using git's native SSH signing (`gpg.format=ssh`). The user's Ed25519 private key is written to a temp file (`temp_signing_key` context manager), and the public key hex is embedded in the commit message as a `Pubkey:` trailer:

```
commit abc123…
Author: User Name <user-id@peerpedia>

update article content

Pubkey: a1b2c3d4e5f6…
```

Verification uses `git verify-commit` with an `allowed_signers` file built from the embedded pubkey. The platform user (`system@peerpedia`) is exempt — its commits are status markers and carry no signature.

**Git config** (set via env vars, not `-c` flags, because git >= 2.44 rejects `-c` after the subcommand):
```
GIT_CONFIG_COUNT=3
GIT_CONFIG_KEY_0=gpg.format          → "ssh"
GIT_CONFIG_KEY_1=gpg.ssh.allowedSignersFile → <temp allowed_signers>
GIT_CONFIG_KEY_2=user.signingkey      → <temp private key path>
```

### Anonymous review IDs (HMAC-SHA256 derivation)

During sedimentation (before publication), reviewer identities are hidden in the git filesystem. The review directory name is a deterministic hash — not the reviewer's real UUID:

```python
def _derive_anonymous_id(article_id, signing_key):
    # SHA-256(article_id : normalized_reviewer_id) → first 12 hex chars
    h = hashlib.sha256(f"{article_id}:{reviewer_id}".encode()).hexdigest()
    return h[:12]
```

- **Sedimentation review**: git dir=`anon_hash`, DB `reviewer_id`=real UUID
- **Published review**: git dir=real UUID, DB `reviewer_id`=real UUID

The anonymous directory name and the real DB reviewer_id are linked only through the commit — when the article publishes, the mapping is resolved. The `derive_anonymous_name(seed)` function turns the hash into a human-readable name like "量子上古" for display.

### Sedimentation pool (timer mechanism, not cron)

The sedimentation pool is a timer-based mechanism, not a cron job. Each article in sedimentation has a `sink_eta` timestamp. The REPL's event loop checks every `scan_interval_seconds` (default 3600s):

```python
# In REPL event loop:
for article in sedimentation_articles:
    if is_ready_to_publish(article.sink_eta):  # now >= sink_eta?
        publish_article(db, article.id, ...)
```

Parameters (from `SinkParams`):
- `new_article_default_days`: 7 — initial sink period for new articles
- `edit_article_default_days`: 3 — sink period reset after an edit
- `min_days`: 2 — minimum sink, even with high scores
- `max_days`: 180 — absolute maximum
- `min_approvals`: 3 — reviewers needed to avoid `review_deficit_extend_days`
- `review_deficit_extend_days`: 3 — extra sink if not enough reviewers
- `max_total_sink_days`: 21 — hard cap including extensions
- `max_sedimentation_per_author`: 5 — anti-spam limit on concurrent articles in pool

The `apply_no_review_penalty` function subtracts 0.5 from each score dimension if the article received zero reviews during sedimentation.

## Data Flow Diagrams

### Article creation flow

```
CLI                         commands/                 storage/git_backend          storage/db
────                        ────────                  ────────────────────         ──────────
_cmd_article_create
  │                          create_article_
  │                          with_content(db,
  │                            author_id, title,
  │                            content, format,
  │                            signing_key)
  │                            │
  │                            ├──► init_article_repo(path)
  │                            │     • mkdir repo_path
  │                            │     • git.Repo.init()
  │                            │     • write .gitignore
  │                            │     • initial commit
  │                            │     returns Path
  │                            │
  │                            ├──► write article.md / article.typ
  │                            │     (frontmatter + body)
  │                            │
  │                            ├──► temp_signing_key(key) → key_path
  │                            ├──► commit_article(path, msg,
  │                            │       author, email,
  │                            │       signing_key=key_path,
  │                            │       pubkey_hex=hex)
  │                            │     • git add -A
  │                            │     • git commit -S (SSH-signed)
  │                            │     returns commit_hash
  │                            │
  │                            ├──► crud_article.create_article(db, ...)
  │                            │     INSERT INTO articles ...
  │                            │
  │                            ├──► crud_maintainer.add_maintainer(db,
  │                            │       article_id, author_id)
  │                            │
  │                            └──► returns article_id
  │
  ◄── display article
```

### Publish flow (draft → sedimentation → published)

```
  draft ──► sedimentation ──► published
             (timer loop)       │
                                ├──► commit_status_marker([status] published)
                                │     (platform commit, unsigned)
                                │
                                ├──► update_article_status(db, "published")
                                │
                                ├──► recompute_article_score(db, id)
                                │     • aggregate_review_scores(reviews)
                                │     • crud_article.update_article_score(db)
                                │
                                ├──► create_notifications_batch(db, ...)
                                │     (notify all followers)
                                │
                                └──► returns article_view

  Timer-based auto-publish (REPL event loop):
    for article in crud_article.list_articles(db,
                      status="sedimentation"):
        if is_ready_to_publish(article.sink_eta):
            publish_article(db, article.id, ...)
```

### Sync flow (client ↔ server bundle exchange)

```
CLIENT (sync_article)                           SERVER (transport/routes)
─────────────────────                           ──────────────────────────
  fetch_head(url, article_id)
    ──GET /articles/{id}/head──────────────────►  get_article_head(id)
    ◄── {"hash": "abc123"} (or 404)               read git HEAD

  (if 404 — first time upload)
  upload_article(url, id, repo_path)
    ──POST /articles (tar.gz)──────────────────►  ingest_first_article(tar)
    ◄── 201 Created                                unpack → git init

  (else — incremental sync)
  local_commits = get_commit_history(local_repo)
  merge_base = find_merge_base(server, id,
                               local_commits)
    │ k-exponential probes:
    └──► for i in [1, 5, 25, …]:
          GET /articles/{id}/ancestor/{hash}───►  check_article_ancestor(id, hash)
          ◄── {"is_ancestor": true/false}          git merge-base --is-ancestor

  ┌── Server ahead:
  │   pull_incremental(url, id, merge_base)
  │     ──GET /articles/{id}/bundle?since={h}──►  get_article_bundle(id, since)
  │     ◄── <git bundle bytes>                     create_bundle(repo, since)
  │     ingest_bundle(local_repo, bundle_bytes)
  │
  └── Local ahead:
      push_incremental(url, id, server_head,
                       local_repo)
        create_bundle(local_repo, server_head)
        ──POST /articles/{id}/sync───bundle────►  apply_sync(id, bundle_bytes)
        ◄── 200 OK                                 ingest_bundle(repo, bundle)
                                                   (ff_only=True)

  409 Conflict: pull first → merge → push again

  apply_sync_bundle(db, article_id)
    • sync_reviews_from_worktree(db, id)
    • sync_status_from_git(db, id)
    • recompute_article_score(db, id)
```

### Review flow (submit → git → DB → score recompute)

```
CLI                              commands/reviews.py
────                              ────────────────────
_cmd_review_submit
  │                                submit_review(db, article_id,
  │                                  reviewer_id, scores,
  │                                  comment, signing_key)
  │                                  │
  │                                  ├── policies.assert_can_submit_review
  │                                  ├── assert_not_folded
  │                                  │
  │                                  ├── [if sedimentation]
  │                                  │   anon_id = _derive_anonymous_id(
  │                                  │                article_id, reviewer_id)
  │                                  │   display = derive_anonymous_name(anon_id)
  │                                  │   dir = anon_id
  │                                  │
  │                                  ├── write_review_to_git(article_id,
  │                                  │     dir, scores, comment,
  │                                  │     display, email, signing_key)
  │                                  │   │
  │                                  │   ├── get_article_lock(id)
  │                                  │   ├── write reviews/{dir}/scores.json
  │                                  │   ├── write reviews/{dir}/threads/{n}.md
  │                                  │   ├── commit_article(path, msg,
  │                                  │   │     signing_key=key_path)
  │                                  │   │     • git add -A
  │                                  │   │     • git commit -S
  │                                  │   │     returns commit_hash
  │                                  │   └── return commit_hash
  │                                  │
  │                                  ├── crud_review.upsert_review(db,
  │                                  │     article_id, commit_hash,
  │                                  │     reviewer_id, scores)
  │                                  │     INSERT OR REPLACE INTO reviews
  │                                  │
  │                                  ├── commands.workflow.
  │                                  │     recompute_article_score(db, id)
  │                                  │   │
  │                                  │   ├── workflow.scoring.
  │                                  │   │     aggregate_review_scores(
  │                                  │   │       reviews, author_ids,
  │                                  │   │       weight_self=0.15,
  │                                  │   │       weight_community=0.85)
  │                                  │   ├── [if no reviews] sedimentation.
  │                                  │   │     apply_no_review_penalty(scores)
  │                                  │   └── crud_article.update_article_score
  │                                  │
  │                                  ├── for each author_id:
  │                                  │     recompute_author_reputation(db, id)
  │                                  │       • compute_reputation(snapshot)
  │                                  │       • crud_user.update_user_reputation
  │                                  │
  │                                  └── create_notification(authors,
  │                                        "new_review", ...)
```

### Social graph sync

```
CLI (social.py)         social/exchange.py            transport/              commands/discover.py
───────────────         ──────────────────           ──────────              ────────────────────
_cmd_school()
  │
  ├── for each known server:
  │     _pull_social(db, server, me, key)
  │       │
  │       └── discover_following(db, server,
  │               my_id, signing_key)
  │             │
  │             ├── fetch_following(server, my_id)
  │             │   ──GET /users/{id}/following──►  http_client.py:
  │             │   ◄── [...]                          httpx.get()
  │             │
  │             └── merge_follows(db, following)
  │                   │
  │                   ├── crud_user.get_user(db, fid)
  │                   ├── [if not exists] merge_users() → create_user_stub
  │                   └── crud_user.follow_user(db,
  │                         my_id, fid)
  │
  ├── discover_followers(db, server, my_id, key)
  │     ├── fetch_followers(server, my_id)
  │     └── merge_followers(db, followers)
  │
  ├── discover_articles(db, server, my_id, key)
  │     ├── fetch_user_articles(server, my_id)
  │     └── merge_article_meta(db, articles)
  │
  └── discover_shares(db, server, my_id, key)
        ├── fetch_shares(server, my_id)
        └── merge_shares(db, shares)
```
