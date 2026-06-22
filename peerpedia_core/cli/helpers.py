# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Shared infrastructure for CLI handlers — DB, editor, messaging, user resolution.

Layer 1 of the CLI package.  Imports from ``display`` (Layer 0) and
``commands/`` (external).  Does NOT import from handlers or parser.
"""

from __future__ import annotations

import functools
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from peerpedia_core.cli.display import console, theme
from peerpedia_core.commands import db_session, get_user_by_name

DEFAULT_ARTICLES_DIR = Path.home() / ".peerpedia" / "articles"

# ── Database ─────────────────────────────────────────────────────────────

DB_PATH = Path.home() / ".peerpedia" / "peerpedia.db"
DB_URL = f"sqlite:///{DB_PATH}"


def _with_db(func):
    """Helper for all command functions: gives them a database session.

    Every ``_cmd_*`` function in this file needs a ``db`` to do its job.
    This helper opens the database, passes it to the function, commits on
    success, rolls back on failure, and closes the connection afterwards.

    Usage: add ``@_with_db`` above a command function, and add ``db`` to its
    signature.  The decorator injects the database session automatically.

    >>> @_with_db
    ... def _cmd_article_create(db, args):
    ...     create_article_with_content(db, ...)  # db is ready to use
    """

    @functools.wraps(func)
    def wrapper(args):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            with db_session(DB_URL) as db:
                return func(db, args)
        except Exception as e:
            _die(str(e))

    return wrapper


# ── Output formatting — messages ────────────────────────────────────────


def _page(text: str) -> None:
    """Display text through a pager (``$PAGER`` or ``less -R``).

    Uses the pager for long content so the user can scroll.  Falls back to
    direct print when the pager is unavailable (e.g. in tests).
    """
    pager = os.environ.get("PAGER", "less -R")
    try:
        proc = subprocess.run(
            pager.split(), input=text, text=True, timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        console.print(text)


def _open_file(path: str) -> None:
    """Open a file with the system default application."""
    if sys.platform == "darwin":
        subprocess.run(["open", path])
    elif sys.platform == "win32":
        os.startfile(path)  # noqa: S606 — intentional user-facing file open
    else:
        subprocess.run(["xdg-open", path])


def _ok(what: str) -> None:
    """Success message with green checkmark."""
    console.print(f"✓ [{theme.styles['success']}]{what}[/]")


def _die(msg: str) -> None:
    """Error message with red cross, then exit."""
    console.print(f"✗ [{theme.styles['error']}]{msg}[/]")
    sys.exit(1)


def _json_out(data: dict | list) -> None:
    """Machine-readable output, used when --json is passed."""
    print(json.dumps(data, indent=2, default=str))


# ── Shared logic — reused by multiple commands ──────────────────────────


def _find_article_file(article_id: str) -> Path:
    """Find the source file for an article. Raises if not found."""
    rp = DEFAULT_ARTICLES_DIR / article_id
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            return f
    _die(f"No source file found for article {article_id}")


def _resolve_user(db, user_ref: str | None) -> str:
    """Resolve a user reference to a user ID.

    ``None`` → read current user from ``~/.peerpedia/session.json``.
    ``@name`` → look up username in local DB.
    UUID or UUID prefix → pass through directly (no DB check).
    """
    if user_ref is None:
        session_file = Path.home() / ".peerpedia" / "session.json"
        if session_file.exists():
            session = json.loads(session_file.read_text())
            user_ref = session.get("user_id")
            if user_ref:
                return user_ref
        _die("No user specified. Register first:\n"
             "  peerpedia account register --name <your-name>\n"
             "Or pass an explicit user:\n"
             "  --user @name  or  --user <uuid>")
    if user_ref.startswith("@"):
        u = get_user_by_name(db, user_ref[1:])
        if u:
            return u.id
        _die(f"User '@{user_ref[1:]}' not found.\n"
             f"  Register: peerpedia account register --name {user_ref[1:]}")
    # UUID or UUID prefix — pass through.
    return user_ref


def _resolve_user_with_key(db, user_ref: str | None) -> tuple[str, bytes | None]:
    """Resolve user reference to (user_id, private_key_bytes | None).

    Like _resolve_user, but also reads the private key from the session file.
    Returns None for the key if no session exists or the session has no key
    (e.g., pre-auth-migration sessions).
    """
    user_id = _resolve_user(db, user_ref)
    session_file = Path.home() / ".peerpedia" / "session.json"
    key_bytes = None
    if session_file.exists():
        session = json.loads(session_file.read_text())
        key_hex = session.get("private_key_hex")
        if key_hex:
            key_bytes = bytes.fromhex(key_hex)
    return user_id, key_bytes


def _parse_scores(scores_str: str | None) -> dict | None:
    """Parse "orig=4,rigor=3,..." from command-line into a dict."""
    if not scores_str:
        return None
    return {
        k.strip(): int(v.strip())
        for part in scores_str.split(",")
        for k, v in [part.strip().split("=")]
    }


def _prompt_commit_message(diff: str = "") -> str:
    """Open ``$EDITOR`` to get a commit message, like ``git commit``.

    Shows a template with the diff below ``#`` comment lines so the
    user can review what changed before writing the message.
    Empty messages are rejected.
    """
    header = (
        "\n# Please enter a commit message for your changes.\n"
        "# Lines starting with '#' will be ignored.\n"
        "# An empty message aborts the commit.\n"
        "#\n"
    )
    if diff:
        header += "# Changes:\n#\n"
        for line in diff.splitlines():
            header += f"# {line}\n"
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as f:
        f.write(header)
        f.flush()
        subprocess.call([editor, f.name])
        text = Path(f.name).read_text()
    lines = [l for l in text.splitlines() if not l.strip().startswith("#")]
    msg = "\n".join(lines).strip()
    if not msg:
        _die("Aborting: empty commit message.")
    return msg


def _open_editor(initial: str) -> str:
    """Open $EDITOR (defaults to vim) and return the edited text.

    Users set their preferred editor via the EDITOR environment variable:
      export EDITOR=nano    # add to ~/.zshrc or ~/.bashrc
      EDITOR=code peerpedia article create --title "Hello"  # one-off
    """
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(initial)
        f.flush()
        subprocess.call([editor, f.name])
        return Path(f.name).read_text()
