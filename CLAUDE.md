## Always stash uncommited file before switching branches

Always be careful on the branch.
You can easily lose files if you do not commit important ones before switching branches.
If you lost files, I will treat it as delibrate and you do it **intentionally**.

## Do not write fallback functions or parameters
Fail fast. 
If you let the fallback happen, you are **lying** and trying to hide mistakes.
If a parameter should not be none, throw error when it is.

## Think more before coding
State assumptions explicitly. If uncertain, ask rather than guess.
Present multiple interpretations when ambiguity exists.
Push back when a simpler approach exists.
Stop when confused. Name what's unclear.
If you code before thinking, you are IDOIT!


## Goal-Driven Execution
Define success criteria. Loop until verified.
Don't follow steps. Define success and iterate.
Strong success criteria let you loop independently.

## Tests verify intent, not just behavior
Tests must encode WHY behavior matters, not just WHAT it does.
A test that can't fail when business logic changes is wrong.

## Double check my meaning
If you are not sure about my meaning, ask.
Do not pretend you have understood it.
You are idiot if you do not ask me and do it brutally.


## Architecture

```
cli/          User commands — imports commands/ + transport/, never storage/
  ↓
commands/     Business logic — ONLY layer that calls storage/db/crud_*
  ↓
storage/db/   SQLite (SQLAlchemy) — CRUD + models + engine
storage/      Git backend (git_backend.py) — pure git, no DB

transport/    HTTP client+server — ONLY layer importing httpx/starlette
bundle/       Git bundle protocol — push/pull article repos (tar.gz, bundle)
social/       Social graph exchange — follow/unfollow propagation via HTTP
workflow/     Pure compute — scoring, reputation, sedimentation (no IO)
```

### Import rules (enforced by tests/test_architecture.py)
- `transport/http_client.py` + `transport/health.py` only: `import httpx`
- `storage/git_backend.py` + `bundle/git_bundle.py` only: `import git`
- `storage/db/` only: `import sqlalchemy`
- `commands/` + `storage/db/` only: import from `storage/db/crud_*.py`
- `bundle/client.py` + `bundle/server.py` + `bundle/__init__.py` only: import from `bundle/git_bundle.py`
- Foundation modules (`config/`, `policies/`, `storage/`, `workflow/`, `types/`, `compiler.py`, `crypto.py`, `exceptions.py`, `frontmatter.py`, `repl.py`) must NOT import from `bundle/`, `social/`, `transport/`

### Naming conventions
- `fetch_*` = HTTP GET from remote server → data or None
- `push_*` = HTTP POST to remote server → None/True or raises
- `pull_*` = download + store locally (git repo)
- `discover_*` = fetch from peer + merge into local DB
- `merge_*` = insert/update local DB from peer data (commands/discover.py)

### Auth
Ed25519 key pairs (same as git commit signing). HTTP requests carry
`Authorization: Peerpedia <uid>:<ts>:<body_sha256>:<sig>`. Server
verifies against user's stored public key. ±30s replay window.

### Sync protocol (sync_article)
1. `fetch_head` → server HEAD (404 → first-time upload)
2. k-exponential probe `ancestor_probe` → find common ancestor
3. `fetch_incremental_bundle` (server ahead) or `push_bundle` (local ahead)
4. Server records `witnessed_at` timestamp for priority disputes
5. Clock skew >30s → hard block (refuse sync)

### Key files
commands/__init__.py  transport/http_server.py  bundle/client.py  storage/db/models.py
