# PeerPedia Core — Architecture

## File Tree

```
peerpedia_core/
├── compiler.py               # Compiler backend (Markdown/Typst → HTML/PDF/SVG/PNG)
├── crypto.py                  # Ed25519 key derivation, signing, verification
├── exceptions.py              # Semantic exceptions (NotFound, NotAuthorized, Conflict, etc.)
├── frontmatter.py             # YAML frontmatter parse/build
├── repl.py                    # Interactive REPL (prompt_toolkit + timed scan)

├── config/
│   ├── paths.py               # Centralised filesystem paths (PEERPEDIA_HOME env override)
│   ├── git.py                 # Git config helpers (gitignore, SSH signing env)
│   └── params.py              # Tunable parameters (sink days, score weights)

├── types/
│   └── scores.py              # FiveDimScores, ReputationScores, SCORE_DIMENSIONS

├── policies/
│   └── articles.py            # Permission checks (read/write/fork/publish/rollback/sync/review/reply/merge)

├── storage/                   # Local persistence
│   ├── git_backend.py         #   Git operations (init/commit/history/diff/merge/clone/verify)
│   ├── locks.py               #   File-based lock for concurrent git writes
│   └── db/
│       ├── engine.py            #   SQLAlchemy engine, JSONList/JSONDict types, migrations
│       ├── models.py            #   ORM: Article, User, Review, Follow, Alias, Share,
│       │                        #        Bookmark, MergeProposal, Citation, Notification
│       ├── session_utils.py     #   Transaction lifecycle (commit/rollback/close)
│       ├── crud_article.py    #   Article CRUD + publish_consents
│       ├── crud_user.py       #   User, Follow, anonymous names
│       ├── crud_review.py     #   Review score cache
│       ├── crud_maintainer.py #   Maintainer membership
│       ├── crud_merge.py      #   MergeProposal CRUD
│       ├── crud_citation.py   #   Citation edge CRUD
│       ├── crud_bookmark.py   #   Bookmark CRUD
│       ├── crud_share.py      #   Share CRUD
│       ├── crud_alias.py      #   Alias CRUD (local nicknames)
│       └── crud_notification.py # Notification CRUD

├── commands/                  # Orchestration — only layer touching both git and db
│   ├── __init__.py            #   Facade: re-exports all public functions
│   ├── users.py               #   User lifecycle + follow/unfollow
│   ├── notifications.py       #   Notification facade
│   ├── discover.py            #   P2P social graph merge (users, follows, articles, shares)
│   ├── views.py               #   Response-ready dicts for API
│   ├── integrity.py           #   Article integrity verification (commit signatures, DB/git consistency)
│   ├── workflow.py            #   publish_ready_articles, recompute_article_score, recompute_author_reputation
│   ├── bundle.py              #   apply_sync_bundle, sync_reviews_from_worktree
│   ├── reviews.py             #   submit_review, submit_reply, write_review_to_git, _write_thread_message
│   ├── merge.py               #   accept_merge, create_merge_proposal, withdraw_merge_proposal
│   ├── maintainers.py         #   add/remove/list maintainers, consent_to_publish, revoke_publish_consent
│   ├── bookmarks.py           #   add/remove/list bookmarks
│   ├── shares.py              #   add/remove/list shares
│   └── articles/
│       ├── __init__.py        #     Read wrappers + re-exports
│       ├── _helpers.py        #     rebuild_article_authors
│       ├── create.py          #     create_article_with_content
│       ├── update.py          #     update_article_content
│       ├── publish.py         #     publish_article
│       ├── fork.py            #     fork_article
│       ├── rollback.py        #     rollback_article
│       ├── delete.py          #     delete_article
│       └── diff.py            #     diff_article + resolve_commit_ref

├── workflow/                  # Pure compute — zero storage dependencies
│   ├── scoring.py             #   aggregate_review_scores (weighted average)
│   ├── sedimentation.py       #   is_ready_to_publish, apply_no_review_penalty
│   ├── reputation.py          #   compute_reputation, blend_reputation, get_reviewer_weight
│   └── state.py               #   Frozen dataclass serialization

├── bundle/                    # Git bundle protocol (push/pull/tar.gz/base64)
│   ├── client.py              #   sync_article, build_push_bundle, pull_incremental
│   ├── server.py              #   Server-side bundle handlers
│   └── pending.py             #   Offline operation queue (add/list/remove/clear)

├── social/                    # P2P social graph exchange
│   └── exchange.py            #   discover_following, discover_followers, discover_articles

├── transport/                 # HTTP — only layer importing httpx/starlette
│   ├── http_client.py         #   fetch_* / push_* (head, bundle, meta, source, social)
│   ├── http_server.py         #   Starlette app with create_app()
│   ├── auth.py                #   Ed25519 auth header signing/verification
│   ├── shared.py              #   Shared HTTP utilities
│   ├── health.py              #   Health check endpoint
│   └── middleware/
│       ├── auth.py            #     Auth middleware (PEERPEDIA_SKIP_AUTH bypass)
│       ├── db.py              #     DB session middleware
│       ├── logging.py         #     Request logging
│       └── ratelimit.py       #     Rate limiter
│   └── routes/
│       ├── articles.py        #     REST routes for articles, search, sync, push
│       └── users.py           #     REST routes for users, social, key rotation

└── cli/                       # Terminal UI — never imports storage/ directly
    ├── __init__.py            #   Entry point: main(), first-run wizard
    ├── parser.py              #   Argparse builder + command table
    ├── helpers.py             #   Shared: _with_db, session, editor, user resolution
    ├── display.py             #   Rich-powered output: panels, tables, diff, stars
    ├── bundle_utils.py        #   Auto-push helpers
    └── handlers/
        ├── account.py         #     register, login, recover, bootstrap, whoami, search
        ├── articles.py        #     create, show, list, edit, publish, delete, scan, diff
        ├── reviews.py         #     submit, list, reply
        ├── maintainers.py     #     add, remove, list, consent, revoke
        ├── notifications.py   #     list, read
        ├── social.py          #     follow, unfollow, bookmark, alias, share, fork, merge
        ├── bundle.py          #     sync status, push, pull
        ├── compile_.py        #     compile
        ├── server.py          #     server start
        └── mother.py          #     ?Mother guide
```

## Layer Rules

```
CLI handlers  ──import──►  commands/       (facade)
Transport     ──import──►  commands/       (facade)
Commands      ──import──►  storage/db/     (CRUD)
Commands      ──import──►  storage/        (git_backend)
Workflow      ──import──►  (nothing)       (pure compute)
Policies      ──import──►  storage/db/     (models only)
Bundle        ──import──►  storage/        (git_backend)
```

- CLI never imports `storage/` directly — goes through `commands/`
- `transport/` is the only layer importing `httpx`/`starlette`
- `storage/db/` is the only layer importing `sqlalchemy`
- `commands/` + `storage/db/` only: import from `storage/db/crud_*.py`
- Foundation modules (config, policies, storage, workflow, types) never import bundle/social/transport

## Key Design Decisions

- **Git-first:** Reviews are written to git before DB — git is source of truth
- **Hash-based sync:** P2P uses commit hashes, not branch refs
- **Single-mainline:** Article repos use `refs/heads/main` only
- **Scrypt key derivation:** Password + salt → Ed25519 key pair
- **TOFU auth:** First-use trust for peer public keys
- **Local-first:** All operations work offline; sync is explicit
