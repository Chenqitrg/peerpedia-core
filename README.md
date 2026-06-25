# PeerPedia Core

同行评审基础设施 -- 命令行工具 + Python 库，用于写论文、互相评审、公开发布。

**Git stores content; SQLite stores state.** Every article is an independent Git repository -- body text and reviews have full history, can be diffed/forked/merged. Metadata (status, scores, relationships) lives in SQLite for fast queries and aggregation.

[![Tests](https://github.com/Chenqitrg/peerpedia-core/actions/workflows/test.yml/badge.svg)](https://github.com/Chenqitrg/peerpedia-core/actions/workflows/test.yml)
617 tests | 69% coverage | Python 3.11+

## Installation

```bash
pip install peerpedia-core
```

Dependencies: Python 3.11+, Git. SQLite database is created automatically at `~/.peerpedia/`.

### Tab completion

```bash
# zsh (add to ~/.zshrc)
autoload -U bashcompinit && bashcompinit
eval "$(register-python-argcomplete peerpedia)"
```

## 5-minute quickstart

### 1. Register an account

```bash
peerpedia account register --name "Alice"
# -> Registered Alice (id: eef0e359)
```

All data lives locally in `~/.peerpedia/peerpedia.db`. No server required. Keys are derived from password + scrypt, recoverable across devices.

### 2. Write an article

```bash
peerpedia article create --title "A Note on Tensor Networks" --content "# Intro\n\n..."
```

Omit `--content` to open `$EDITOR`.

### 3. Publish to the sedimentation pool

```bash
peerpedia article publish <id> --scores "originality=4,rigor=3,completeness=4,pedagogy=3,impact=4"
```

Sedimentation is PeerPedia's review mechanism: articles enter a timed public review period (7 days first time), then auto-publish when the timer expires.

### 4. Review

```bash
peerpedia review submit <id> --scores "..." --comment "Well-structured."
peerpedia review reply <id> --to @reviewer
peerpedia review invite <id> --user <reviewer-id>
peerpedia review rate <id> --reviewer <reviewer-id> --helpfulness 4
```

### 5. Fork & Merge

```bash
peerpedia fork <id>                 # Fork a published article
peerpedia merge propose <fork-id> --target <original-id>
peerpedia merge accept <proposal-id> --target <article-id>
```

### 6. Multi-device setup

```bash
# Device A: export identity
peerpedia account whoami --verbose --json
# -> {"user_id":"...","name":"Alice","public_key":"...","salt":"..."}

# Device B: import identity and recover
peerpedia account bootstrap --from '<json>' --peer https://peer.example.com
peerpedia account recover --user-id <id>
```

On device B, `account login --peer <url> --user-id <uuid>` remotely fetches the user stub from the peer server and sets up credentials without the original device:

```bash
peerpedia account login --name "Alice" --peer https://peer.example.com --user-id eef0e359
```

After bootstrapping, `peerpedia sync pull --server <url>` pulls articles from the peer automatically.

### 7. Delete your account

```bash
peerpedia account delete
```

This performs a soft delete -- user data is preserved locally for others' references, but the account is deactivated and the session file removed.

### 8. Diff & discover

```bash
peerpedia article diff <id> HEAD ~1         # diff most recent change
peerpedia article list --server <url> --user <id>  # discover remote articles
```

## State machine

```
draft --publish()--> sedimentation --auto-expire--> published
                          ^                             |
                          |    edit / merge              |
                          +-----------------------------+
                              (auto 3-day sedimentation)
```

## Command reference

### account -- Account management

| Command | Description |
|---------|-------------|
| `account register --name <name>` | Register a new user |
| `account login --name <name>` | Login (local) |
| `account login --name <name> --peer <url> --user-id <uuid>` | Login with remote bootstrap (new device) |
| `account delete` | Soft-delete the current account |
| `account recover [--name <n>\|--user-id <id>]` | Recover keys from password |
| `account bootstrap --from '<json>' [--peer <url>]` | Import identity on a new device |
| `account whoami [--verbose]` | Show current user (--verbose shows public key and salt) |
| `account search <query>` | Search users |

### article -- Article management

| Command | Description |
|---------|-------------|
| `article create --title <t> [--content <c>] [--no-editor]` | Create a draft |
| `article create ... --publish --scores <s>` | Create and immediately publish |
| `article show <id> [--show meta\|full]` | View an article |
| `article list [--status <s>] [--mine] [--feed] [--bookmarked]` | List articles (local) |
| `article list --user <id> [--server <url>]` | Discover articles from a remote user |
| `article edit <id> [--content <c>] [--title <t>]` | Edit an article |
| `article publish <id> --scores <s>` | Publish to the sedimentation pool |
| `article delete <id>` | Delete a draft |
| `article diff <id> <hash1> <hash2>` | Diff two versions |
| `article scan` | Trigger auto-publish for expired sedimentation articles |

### review -- Reviews

| Command | Description |
|---------|-------------|
| `review submit <id> --scores <s> [--comment <c>]` | Submit a review |
| `review invite <id> --user <user-id>` | Invite a specific user to review |
| `review rate <id> --reviewer <user-id> --helpfulness <1-5>` | Rate a review's helpfulness |
| `review list <id> [--show meta\|full]` | List reviews (full shows threads) |
| `review reply <id> --to <reviewer>` | Reply to a review (bidirectional conversation) |

### maintainer -- Co-authorship

| Command | Description |
|---------|-------------|
| `maintainer add <id> --target-user <uid>` | Add a co-author |
| `maintainer remove <id> --target-user <uid>` | Remove a co-author |
| `maintainer list <id>` | List co-authors |
| `maintainer consent <id>` | Consent to publish/merge (unanimous required) |
| `maintainer revoke <id>` | Revoke consent |

### notifications

| Command | Description |
|---------|-------------|
| `notifications [--all]` | View notifications (default: unread only) |
| `notifications read <id>` | Mark a notification as read |

### social -- Social graph

| Command | Description |
|---------|-------------|
| `follow <user>` | Follow a user |
| `unfollow <user>` | Unfollow a user |
| `following --user <id> [--server <url>]` | View who a user follows |
| `followers --user <id> [--server <url>]` | View a user's followers |
| `school [--limit <n>] [--server <url>] [--local]` | Top users by follower count (default: 20) |
| `bookmark add <id>` | Bookmark an article |
| `bookmark remove <id>` | Remove a bookmark |
| `share add <id> [--to <user>] [--comment <c>]` | Share an article |
| `share list [--mine]` | List shares |
| `share remove <id>` | Remove a share |
| `alias set <user> <alias>` | Set a local alias for a user |
| `alias remove <user>` | Remove an alias |
| `alias list` | List all aliases |

### merge / fork

| Command | Description |
|---------|-------------|
| `fork <id>` | Fork a published article into a new draft |
| `merge propose <fork-id> --target <target-id>` | Propose a merge from a fork |
| `merge accept <proposal-id> --target <id>` | Accept a merge proposal |
| `merge withdraw <proposal-id>` | Withdraw a merge proposal |

### sync -- Peer-to-peer synchronization

| Command | Description |
|---------|-------------|
| `sync status [--server <url>]` | Show synchronization status between local and peer |
| `sync push [--server <url>]` | Push local offline operations to the peer server |
| `sync pull [--server <url>]` | Pull article updates from the peer server |

Syncing uses a k-exponential probe protocol to find a common git ancestor, then exchanges incremental git bundles. Clock skew exceeding 30 seconds is hard-blocked. Each sync records a `witnessed_at` timestamp on the server for priority dispute resolution.

### Others

| Command | Description |
|---------|-------------|
| `compile <id> [--format pdf\|svg\|png\|html]` | Compile an article to a rendered format |
| `server start [--host <h>] [--port <p>]` | Start the HTTP peer server |

### General flags

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--version` | Show version |

## Scoring dimensions

| Dimension | Meaning |
|-----------|---------|
| originality (原创性) | How novel is the idea? |
| rigor (严谨性) | How sound is the argument? |
| completeness (完整性) | How thorough is the work? |
| pedagogy (教学性) | How clearly is it written? |
| impact (影响力) | How much potential impact? |

## Notification events

All events generate local notifications viewable via `peerpedia notifications`:

| Event | When it fires |
|-------|---------------|
| `article_published` | An article you follow or reviewed is published |
| `review_submitted` | Your article receives a review |
| `review_reply` | The author replies to your review |
| `review_invitation` | You are invited to review an article |
| `merge_proposed` | Someone proposes a merge to your article |
| `merge_accepted` | Your proposed merge was accepted |
| `new_follower` | Someone follows you |

## Architecture

```
cli/ + repl.py          -- Entry layer: parse args, dispatch, commit()
    |
commands/               -- Orchestration: the only layer touching both git and DB
    |
    +-- storage/        -- git_backend (content) + db/ (metadata), not aware of each other
    +-- workflow/       -- Pure compute: scoring, reputation, sedimentation logic
    +-- policies/       -- Authorization checks (maintainer-only, ownership, etc.)
    +-- bundle/         -- P2P sync: git bundle protocol (probe, incremental bundles)
    +-- transport/      -- HTTP client + server (httpx + starlette)
    +-- social/         -- Social graph exchange (follow/unfollow propagation)
```

Each layer has a single responsibility. **cli/** handles argument parsing and delegates to `commands/` -- never imports from storage or transport. **commands/** is the orchestration hub: the only layer that touches both git and the database. **storage/db/** is pure SQLAlchemy data access (only directory that may `import sqlalchemy`). **storage/git_backend.py** handles raw git operations (only file that may `import git`). **transport/** is HTTP (httpx + starlette), translating requests into `commands/` calls. **bundle/** implements the git bundle sync protocol (probe, incremental bundles). **workflow/** contains stateless pure functions for scoring and sedimentation -- no I/O. **social/** handles follow propagation, alias resolution, and school ranking. Foundation modules (`config/`, `policies/`, `types/`, `exceptions.py`, `crypto.py`, `frontmatter.py`) must not import from `bundle/`, `social/`, or `transport/`. These import rules are enforced by `tests/test_architecture.py`.

## Data directory

```
~/.peerpedia/
+-- peerpedia.db          -- SQLite (metadata, notifications, relationships)
+-- session.json          -- Current session (private key, chmod 600)
+-- pending_ops.json      -- Offline operation queue
+-- articles/
    +-- {article_id}/
        +-- .git/          -- Git repository
        +-- article.md     -- Article body
        +-- reviews/
            +-- {reviewer}/
                +-- scores.json
                +-- threads/
                    +-- 001.md
                    +-- 002.md   -- Author reply
                    +-- ...
```

## Design principles

1. **Local-first** -- Everything works offline. Git operations and metadata queries never require a network. The peer server is optional, for sync and discovery.

2. **Git-first** -- Content lives in Git repositories. Every change has full version history. Git is the source of truth for article content and review threads.

3. **TOFU auth** -- Trust on first use. When syncing with a peer for the first time, the peer's public key is stored. Subsequent connections verify the same key. No central certificate authority.

4. **Single-mainline** -- Each article has one authoritative `.git` history. Forks create separate repositories; merge proposals are the only way to bring changes back into the mainline.

5. **Hash-based sync** -- Sync finds a common ancestor via k-exponential probe of commit hashes, then exchanges incremental git bundles. No central index, no global state.

6. **Explicit over implicit** -- No auto-discovery of peers, no ambient sharing. All follows, shares, and sync operations are explicit user actions. Notifications are local only; you opt in to every relationship.

## Using as a Python library

```python
from peerpedia_core.commands import (
    create_article_with_content,
    publish_article,
    submit_review,
    submit_reply,
    invite_reviewer,
    rate_review_helpfulness,
    create_user_stub,
    create_notification,
    create_merge_proposal,
    accept_merge,
    fork_article,
    follow_user,
    unfollow_user,
)
from peerpedia_core.crypto import derive_keypair, sign_message, verify_signature
from peerpedia_core.types import UserStub, ArticleRecord, ReviewRecord
from peerpedia_core.exceptions import NotFoundError, NotAuthorizedError, BadRequestError
```

All commands take an SQLAlchemy `Session` as the first parameter, making them testable and embeddable.

## Development

```bash
git clone https://github.com/Chenqitrg/peerpedia-core.git
cd peerpedia-core
pip install -e ".[dev]"
pytest tests/ -v           # 617 tests
pytest tests/ -x --lf      # Re-run failures only (fast feedback)
```

Architecture import rules are verified by `tests/test_architecture.py` -- run it before opening a PR.

## License

CC BY-NC-SA 4.0 with Anti-AI Training Addendum. See [LICENSE](LICENSE).
Copyright (c) 2024-2026 Chenqi Meng and PeerPedia contributors.
