# PeerPedia Core

Peer review infrastructure. Self-contained CLI + Python library for academic paper writing, reviewing, and publishing.

**Git is the source of truth. DB is the index.** Every article is an independent git repository.

## Install

```bash
pip install peerpedia-core
```

## Quick Start

```bash
# Register
peerpedia account register --name "Alice"

# Create an article (opens $EDITOR for content)
peerpedia article create --title "A Note on Tensor Networks" --format markdown

# Publish to the sedimentation pool
peerpedia article publish <id> --scores originality=4,rigor=3,completeness=5,pedagogy=3,impact=4

# Review someone else's article
peerpedia review submit <article-id>

# Fork and merge
peerpedia fork <article-id>
peerpedia merge propose <fork-id> --target <original-id>

# Search
peerpedia search "tensor networks"

# Sync (offline-first)
peerpedia sync status
peerpedia sync push
```

## Commands

```
peerpedia
├── account       register, login, whoami
├── article       create, edit, show, list, publish, delete
├── review        submit, list, reply
├── fork          fork an article
├── merge         propose, accept, reject
├── bookmark      add, list
├── search        full-text search
├── compile       Typst/Markdown → PDF, SVG, HTML
└── sync          status, push, pull
```

All commands support `--json` for machine-readable output.

## Architecture

```
CLI (cli.py) → commands.py → storage/db (SQLAlchemy → SQLite)
                           → storage/git_backend (gitpython → local repos)
                           → policies/ (permission checks)

sync/ → bundle_sync.py (git bundle push/pull)
      → pending_queue.py (offline queue)
      → network.py (online/offline detection)
```

Core functions don't commit transactions — the caller (CLI or backend routes) commits.

## License

CC BY-NC-SA 4.0 with Anti-AI Training Addendum. See [LICENSE](LICENSE).

Copyright (c) 2024-2026 Chenqi Meng and PeerPedia contributors.
