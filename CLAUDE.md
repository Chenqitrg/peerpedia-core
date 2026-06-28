## Always stash uncommited file before switching branches

Always be careful on the branch.
You can easily lose files if you do not commit important ones before switching branches.
If you lost files, I will treat it as delibrate and you do it **intentionally**.

## Do not write fallback functions or parameters
Fail FAST and LOUD. 
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
If you are not sure about my meaning, ASK.
Do NOT pretend you have understood it.
You are IDIOT if you do not ask me and do it brutally.

## Read BEFORE grep-jumping
1. Read the import block (first 40 lines) before editing any file.
2. Read the full function, not just the target line.
3. Check existing functions before adding new ones.
4. No lazy imports. No new wrappers without checking.

## Architecture

```
cli/          User commands — imports core/ + transport/, never storage/
  ↓
core/         Orchestration — merges transport + storage (e.g. sync_article, discover)
  ↓
transport/    P2P protocol — Transport dataclass bundles HTTP callbacks
  http/       HTTP implementation — ONLY layer importing httpx (_core.py)
storage/      Git backend (git/) + DB (db/) + local files (peers.py)
server/       HTTP server — Starlette routes + middleware. Imports core/, never transport/http/
config/       Constants + tunable params (params.py)
workflow/     Pure compute — scoring, reputation, sedimentation (no IO)
```

### Layer rules
- `core/` imports `transport/` (protocol) + `storage/` (git, db).  Never imports `server/`.
- `server/` imports `core/`.  Never imports `transport/http/` directly.
- `transport/http/` imports `httpx`.  Only this directory touches HTTP primitives.
- `storage/db/` imports `sqlalchemy`.  Only this directory touches SQLite.
- Foundation (`config/`, `crypto.py`, `time.py`, `exceptions.py`, `types/`) import nothing from other layers.

### CLI message system (cli/msgs.py)
All user-facing output goes through a centralized registry with structured codes:
```python
_out(args, "REGISTERED", {"id": uid}, name="Alice")     # success → prints ✓, exits 0
_out(args, "AUTH_FAILED")                                 # error → prints ✗, exits 1
_out(None, "W_NO_KNOWN_PEERS")                           # notify → prints, continues
_log("L_SYNC_FAILED", level="warning", server=s, error=e)  # log only
```
- `_out(args, code, data=None, /, **fmt)` — single entry point.  First 3 args are positional-only (/).
- `_log(code, *, level="info", **fmt)` — for background/daemon code (no `args` object).
- Every message has `kind` (SUCCESS/ERROR/NOTIFY/WARNING/INFO), `suggestion`, and `see_also` tuple.
- Add new messages to `cli/msgs.py` `_REGISTRY` dict.  NEVER hardcode error/success strings in handlers.

### CLI handler organization
One file per domain concept, < 250 lines:
- `account.py`, `login.py`, `register.py`, `bootstrap.py` — auth
- `social.py` (follow/unfollow), `share.py`, `alias.py`, `bookmark.py`, `school.py` — social
- `create.py`, `read.py`, `edit.py` — articles (CRUD)
- `fork.py` — fork + merge
- `bundle.py` — sync commands
- `reviews.py`, `notifications.py`, `compile_.py`, `server.py` — misc

### Server middleware order
Request → RateLimit → AuditLog → DBSession → Auth → Route → ErrorHandler
- DBSession skips git-only routes (head, bundle, repo, ancestor).
- Auth skips public routes (school, following, followers, articles, shares).
- Tuneable params in `config/params.py` → `ServerParams`.

### Naming conventions
- `_cmd_*` = CLI command handler (registered in parser.py). `_` prefix = module-private.
- `_out()` / `_log()` = unified output (cli/helpers.py).
- `fetch_*` = HTTP GET from peer. `push_*` = HTTP POST to peer.
- `discover_*` = fetch from peer + store locally. `reconcile_*` = git/DB → compute → write back.

### Auth
Ed25519 key pairs (same as git commit signing). HTTP requests carry
`Authorization: Peerpedia <uid>:<ts>:<body_sha256>:<sig>`. Server
verifies against stored public key (TOFU model). ±30s replay window.

### Sync protocol (core/sync_article.py)
1. `Transport.fetch_head` → server HEAD (404 → first-time upload)
2. k-exponential probe `ancestor_probe` → find common ancestor
3. `fetch_bundle` (server ahead) or `push_bundle` (local ahead)
4. Clock skew >30s → hard block (refuse sync)

### Key files
core/sync_article.py  core/sync_social.py  transport/__init__.py  server/app.py
cli/helpers.py  cli/msgs.py  config/params.py  storage/db/models.py
