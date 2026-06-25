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

from peerpedia_core.cli.display import console, theme, display_article as _render_article
from peerpedia_core.commands import db_session, get_author_ids, parse_frontmatter, resolve_username_or_alias
from peerpedia_core.config.paths import ARTICLES_DIR as DEFAULT_ARTICLES_DIR, DB_PATH, DB_URL, SESSION_FILE


_data_dir_ready = False


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
        global _data_dir_ready
        if not _data_dir_ready:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _data_dir_ready = True
        try:
            with db_session(DB_URL) as db:
                return func(db, args)
        except Exception as e:
            import traceback
            traceback.print_exc()
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


def _resolve_article_id(db, article_ref: str):
    """Resolve an article ID from prefix or fuzzy title match.

    Returns the Article object or calls _die with suggestions.
    """
    article = get_article(db, article_ref)
    if article is not None:
        return article

    # Try prefix match (starts with)
    candidates = list_articles(db, search_query=article_ref, limit=5)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        names = ", ".join(f"{a.id[:8]} ({a.title})" for a in candidates)
        _die(f"Multiple matches for '{article_ref}': {names}")

    _die(f"Article '{article_ref}' not found. Try a title keyword or article ID prefix.")


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


def _resolve_and_display_article(db, article, *, author_ids: list[str] | None = None) -> None:
    """Resolve full article metadata from DB + source file, then display.

    If *author_ids* is passed, it is used directly (allows batch preloading
    in list handlers).  Otherwise ``get_author_ids`` queries the DB.
    """
    raw = _find_article_file(article.id).read_text()
    fm = parse_frontmatter(raw)
    _render_article(
        title=fm.get("title", article.title),
        status=article.status,
        authors=author_ids if author_ids is not None else get_author_ids(db, article.id),
        score=article.score,
        abstract=fm.get("abstract", article.abstract),
    )


def _read_session() -> dict | None:
    """Read the session file, or None if not logged in."""
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text())
    return None


def _write_session(user_id: str, name: str, private_key_hex: str) -> None:
    """Write session file with chmod 600."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps({
        "user_id": user_id,
        "name": name,
        "private_key_hex": private_key_hex,
    }))
    os.chmod(SESSION_FILE, 0o600)


def _get_session_user() -> str:
    """Return the current user ID, or die if not logged in."""
    s = _read_session()
    if s:
        return s["user_id"]
    _die("No user specified. Register first:\n"
         "  peerpedia account register --name <your-name>")


def _resolve_user(db, user_ref: str) -> str:
    """Resolve a user reference to a user ID.

    ``@name`` → look up username first, then aliases.
    UUID or UUID prefix → pass through directly.
    """
    if user_ref.startswith("@"):
        name = user_ref[1:]
        # resolve_username_or_alias checks username first, then falls back
        # to aliases — single query path covers both.  No need for a
        # separate get_user_by_name call.
        session_user = _get_session_user()
        users = resolve_username_or_alias(db, session_user, name)

        if len(users) == 1:
            return users[0].id
        if len(users) > 1:
            candidates = "\n".join(
                f"  {u.id}  {u.name}" for u in users
            )
            _die(
                f"Multiple users match '@{name}':\n{candidates}\n"
                f"Use the UUID to specify which one."
            )
        _die(
            f"User '@{name}' not found.\n"
            f"  Register: peerpedia account register --name {name}\n"
            f"  Or set an alias: peerpedia alias set <user_id> {name}"
        )
    return user_ref


def _get_session_key() -> bytes | None:
    """Return the current user's private key from the session file, or None."""
    s = _read_session()
    if s:
        key_hex = s.get("private_key_hex")
        if key_hex:
            return bytes.fromhex(key_hex)
    return None


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
        header += "# " + "\n# ".join(diff.splitlines()) + "\n"
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
