# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""CLI command modules — thin argparse → app.commands adapters.

Each file corresponds to a user-facing command domain.  Handlers are
``@with_context`` functions named ``_cmd_<command_id with _ for .>``.

**Do not import from this package.**  ``cli/dispatch.py`` lazy-loads
individual modules via ``_HANDLER_MAP`` — that is the single routing
source of truth.

Files:
  account.py       — register, login, recover, whoami, bootstrap, delete, search
  article.py       — create, show, list, edit, publish, delete, scan, diff, compile
  social.py        — follow, unfollow, following, followers, alias, bookmark, share, school
  reviews.py       — submit, list, reply, invite, accept, decline, rate
  fork.py          — fork, merge propose/accept/withdraw
  maintainers.py   — add, remove, list, consent, revoke
  sync.py          — status, pull, discover
  notifications.py — list, read
  server.py        — start
  schema.py        — JSON Schema for AI tool discovery
  help.py          — meta-help
  mother.py        — new-user walkthrough (content in help/mother.txt)
"""
