# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Semantic exceptions -- no HTTP concepts, pure business logic.

Four exception classes, each with a single ``detail: str`` field.  No HTTP
status codes, no headers -- the CLI prints the detail directly; a future
server layer would map these to HTTP status codes.

Exception hierarchy
-------------------
PeerpediaError (base)       ``detail: str``
  ├── NotFoundError          Resource does not exist (article, user, repo)
  ├── NotAuthorizedError     User lacks permission (not author, wrong status)
  ├── ConflictError          State conflict (already forked, article locked)
  └── BadRequestError        Invalid input (empty title, missing self-review)

Usage pattern
-------------
All policy functions (``policies/articles.py``) and orchestration functions
(``commands/``) raise these.  The CLI catches them in command handlers and
calls ``_die(msg)`` to print the error and exit.  The REPL catches them in
``_dispatch`` and prints without exiting.

Reviewer's checklist
--------------------
- Is every new error condition covered by one of these four types?
  If you need a fifth, question whether it's really a new category.
- Does every raise include a human-readable detail string?
"""


class PeerpediaError(Exception):
    """Base for all PeerPedia business-logic errors."""

    def __init__(self, detail: str):
        self.detail = detail


class NotFoundError(PeerpediaError):
    """Requested resource does not exist."""


class NotAuthorizedError(PeerpediaError):
    """User lacks permission for the requested action."""


class ConflictError(PeerpediaError):
    """Request conflicts with the current state of the resource."""


class BadRequestError(PeerpediaError):
    """Input is invalid or missing required data."""
