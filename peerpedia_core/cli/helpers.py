# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Shared infrastructure for CLI handlers — DB, editor, messaging, user resolution.

Layer 1 of the CLI package.  Imports from ``display`` (Layer 0) and
``commands/`` (external).  Does NOT import from handlers or parser.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from peerpedia_core.cli.display import console, theme, display_article as _render_article
from peerpedia_core.commands import (
    assert_article_integrity, count_articles, count_unread_notifications,
    db_repl_setup, db_session, get_article, get_author_ids,
    get_head_hash, get_notifications_for_user,
    get_reviews_for_article, get_top_users_by_followers,
    get_user, get_user_by_name, get_users_by_ids, list_articles, list_users,
    parse_frontmatter, publish_ready_articles, resolve_username_or_alias,
)
from peerpedia_core.config.paths import ARTICLES_DIR as DEFAULT_ARTICLES_DIR, DB_PATH, DB_URL, SESSION_FILE
from peerpedia_core.crypto import load_private_key, _public_key_to_bytes
from peerpedia_core.exceptions import PeerpediaError, TransportError
from peerpedia_core.storage.db.models import Article, User
from peerpedia_core.types.scores import SCORE_DIMENSIONS


_data_dir_ready = False

# Cached DB engine for REPL (REPL keeps a persistent session, unlike CLI's
# one-shot _with_db).  None until first call.
_repl_engine = None
_repl_db = None


def _ensure_db():
    """Return a persistent database session for the REPL.

    Creates the engine on first call; returns the cached session thereafter.
    The REPL owns commit/rollback — this is NOT a context manager.
    """
    global _repl_engine, _repl_db
    if _repl_db is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _repl_engine, _repl_db = db_repl_setup(DB_URL)
    return _repl_db


def _close_db():
    """Close the persistent REPL database session."""
    global _repl_db, _repl_engine
    if _repl_db is not None:
        _repl_db.close()
        _repl_db = None
    if _repl_engine is not None:
        _repl_engine.dispose()
        _repl_engine = None


def _get_article_head_hash(article_id: str) -> str:
    """Return the short HEAD hash for *article_id*, or '' if no repo exists.

    Raises ValueError if the repo exists but has no commits — that is a
    corrupted state (``init_article_repo`` always creates an initial commit).
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    if (rp / ".git").is_dir():
        return get_head_hash(rp)
    return ""


def _with_db(func):
    """Helper for all command functions: gives them a database session.

    Every ``_cmd_*`` function in this file needs a ``db`` to do its job.
    This helper opens the database, passes it to the function, commits on
    success, rolls back on failure, and closes the connection afterwards.

    Usage: add ``@_with_db`` above a command function, and add ``db`` to its
    signature.  The decorator injects the database session automatically.

    >>> @_with_db
    ... def _cmd_article_create(db, args):
    ...     # db session is injected — ready to use with any commands/ function
    ...     pass
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
        except PeerpediaError as e:
            # Expected business-logic error — preserve type information.
            _die(str(e.detail), code=e.code, **e.context)
        except Exception as e:
            import traceback
            traceback.print_exc()
            _die(str(e), code="INTERNAL_ERROR")

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


def _die(msg: str, code: str = "ERROR", *,
         suggestion: str = "", see_also: list[str] | None = None,
         **context) -> None:
    """Error message with actionable guidance, then exit.

    Args:
        msg: Human-readable error description.
        code: Machine-readable error code (e.g. ``"NOT_FOUND"``).
        suggestion: What the user should do next (displayed as a hint).
        see_also: Related commands or topics the user can explore.
        **context: Arbitrary key-value pairs for structured error output.
    """
    from rich.text import Text
    console.print(Text(f"✗ {msg}", style=theme.styles['error']))
    if suggestion:
        console.print()
        console.print(f"  [dim]→ {suggestion}[/]")
    if see_also:
        labels = " · ".join(see_also)
        console.print(f"  [muted]See also: {labels}[/]")
    sys.exit(1)


def _resolve_article_id(db, article_ref: str):
    """Resolve an article by UUID, prefix, or fuzzy title.

    Returns the Article object or calls _die with suggestions.
    """
    # 1. Exact UUID match
    article = db.get(Article, article_ref)
    if article is not None:
        return article

    # 2. UUID prefix match
    candidates = db.query(Article).filter(Article.id.startswith(article_ref)).all()
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        names = ", ".join(f"{a.id[:8]} ({a.title})" for a in candidates)
        _die(f"Multiple ID prefix matches for '{article_ref}': {names}")

    # 3. Title search
    candidates = list_articles(db, search_query=article_ref, limit=5)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        names = ", ".join(f"{a.id[:8]} ({a.title})" for a in candidates)
        _die(f"Multiple title matches for '{article_ref}': {names}")

    _die(f"Article '{article_ref}' not found. Try a title keyword or article ID prefix.")


def _json_out(data: dict | list) -> None:
    """Machine-readable output, used when --json is passed."""
    print(json.dumps(data, indent=2, default=str))


# ── Shared logic — reused by multiple commands ──────────────────────────


def _find_article_file(article_id: str, db=None) -> Path:
    """Find the source file for an article.  Attempts lazy pull if missing.

    When the article was discovered from a peer (stub DB record) but its
    git content hasn't been fetched yet, this function attempts to pull it
    on-demand from PEERPEDIA_SERVER.  If the server is unreachable or not
    configured, the user sees the existing "No source file found" message.

    Raises SystemExit (via _die) if no source file is found after all attempts.
    """
    rp = DEFAULT_ARTICLES_DIR / article_id
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            return f

    # Lazy pull: file doesn't exist locally, try to fetch from peer server.
    server = os.environ.get("PEERPEDIA_SERVER")
    if server and db is not None:
        from peerpedia_core.bundle import pull_new_article
        try:
            pull_new_article(db, server, article_id)
        except TransportError:
            pass  # best-effort: server unreachable, fall through to die
        # Retry after pull
        for ext in [".md", ".typ"]:
            f = rp / f"article{ext}"
            if f.exists():
                return f

    _die(f"No source file found for article {article_id}",
         suggestion="The article may have been discovered from a peer but its "
                    "content hasn't been downloaded yet.  Try 'sync pull' first.")


def _resolve_and_display_article(db, article, *, author_ids: list[str] | None = None) -> None:
    """Resolve full article metadata from DB + source file, then display.

    If *author_ids* is passed, it is used directly (allows batch preloading
    in list handlers).  Otherwise ``get_author_ids`` queries the DB.

    Author UUIDs are resolved to display names for human readability.
    Skips articles without a local source file (discovered stubs) rather
    than crashing — the user sees title/status only.
    """
    author_ids_list = author_ids if author_ids is not None else get_author_ids(db, article.id)
    # Resolve UUIDs to display names.
    author_names = _resolve_author_names(db, author_ids_list)

    try:
        raw = _find_article_file(article.id, db=db).read_text()
    except SystemExit:
        # Article stub without local source — display metadata only.
        _render_article(
            title=article.title,
            status=article.status,
            authors=author_names,
            score=article.score,
            abstract=article.abstract,
        )
        return
    fm = parse_frontmatter(raw)
    _render_article(
        title=fm.get("title", article.title),
        status=article.status,
        authors=author_names,
        score=article.score,
        abstract=fm.get("abstract", article.abstract),
    )


def _read_session() -> dict | None:
    """Read the session file, or None if not logged in or file is corrupted."""
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            logging.getLogger(__name__).warning(
                "Session file %s is corrupted — treating as not logged in",
                SESSION_FILE, exc_info=True,
            )
            return None
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


def _get_session_user_id() -> str:
    """Return the current user ID from session, or '' if not logged in.

    Unlike ``_get_session_user()``, this never calls ``_die`` — callers
    must handle the empty-string case themselves.  Use this for non-fatal
    lookups (e.g., display); use ``_get_session_user()`` for actions that
    require authentication.
    """
    s = _read_session()
    return s["user_id"] if s else ""


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
    UUID or UUID prefix → search DB for matching user.
    """
    if user_ref.startswith("@"):
        name = user_ref[1:]
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

    # Plain string — resolve as UUID, prefix, or exact name match.
    # Exact UUID match
    user = db.get(User, user_ref)
    if user is not None:
        return user.id
    # UUID prefix match
    candidates = db.query(User).filter(User.id.startswith(user_ref)).all()
    if len(candidates) == 1:
        return candidates[0].id
    if len(candidates) > 1:
        names = ", ".join(f"{u.id[:8]} ({u.name})" for u in candidates)
        _die(f"Multiple UUID prefix matches for '{user_ref}': {names}",
             suggestion="Use a longer prefix or the full UUID.")
    # Name match
    candidates = db.query(User).filter(User.name.ilike(f"%{user_ref}%")).all()
    if len(candidates) == 1:
        return candidates[0].id
    if len(candidates) > 1:
        names = ", ".join(f"{u.id[:8]} ({u.name})" for u in candidates)
        _die(f"Multiple users match '{user_ref}': {names}",
             suggestion="Use an @name, a UUID prefix, or try 'account search' first.",
             see_also=["account search"])
    _die(f"User '{user_ref}' not found.",
         suggestion="Check the spelling, use an @name, or search with 'account search'.",
         see_also=["account search", "account register"])


def _get_session_key() -> bytes | None:
    """Return the current user's private key from the session file, or None."""
    s = _read_session()
    if s:
        key_hex = s.get("private_key_hex")
        if key_hex:
            return bytes.fromhex(key_hex)
    return None


def _get_session_pubkey() -> str:
    """Return the current user's Ed25519 public key (hex), derived from the
    session private key.  Returns ``""`` if not logged in."""
    key = _get_session_key()
    if key:
        priv = load_private_key(key)
        pub = priv.public_key()
        return _public_key_to_bytes(pub).hex()
    return ""


def _parse_scores(scores_str: str | None) -> dict | None:
    """Parse "orig=4,rigor=3,..." from command-line into a dict.

    Validates every dimension name (abbreviation or full name) and every
    value against the 1–5 range.  Raises ``_die`` with ``code="BAD_REQUEST"``
    on invalid input — no raw ``ValueError`` escapes.
    """
    if not scores_str:
        return None
    # Build valid-key sets: both abbreviations ("orig") and full names ("originality").
    _valid_abbr = set(SCORE_DIMENSIONS.keys())
    _valid_full = set(SCORE_DIMENSIONS.values())
    _valid = _valid_abbr | _valid_full
    result = {}
    for part in scores_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            _die(f"Malformed score: '{part}' — expected key=value",
                 code="BAD_REQUEST", field="scores", bad_value=part)
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        if k not in _valid:
            abbr_list = ", ".join(sorted(_valid_abbr))
            _die(f"Unknown score dimension: '{k}'. Valid: {abbr_list}",
                 code="BAD_REQUEST", field="scores", bad_dimension=k)
        # Normalize abbreviations to full names (downstream code expects full names).
        if k in _valid_abbr:
            k = SCORE_DIMENSIONS[k]
        try:
            score = int(v)
        except ValueError:
            _die(f"Score for '{k}' must be an integer, got '{v}'",
                 code="BAD_REQUEST", field=f"scores.{k}", bad_value=v)
        if not 1 <= score <= 5:
            _die(f"Score for '{k}' must be 1-5, got {score}",
                 code="BAD_REQUEST", field=f"scores.{k}", bad_value=str(score))
        result[k] = score
    return result


def _prompt_commit_message(diff: str = "") -> str:
    """Open ``$EDITOR`` to get a commit message, like ``git commit``.

    Shows a template with the diff below ``#`` comment lines so the
    user can review what changed before writing the message.
    Empty messages are rejected.
    """
    if not sys.stdin.isatty():
        _die(
            "No TTY available for commit message editor.",
            suggestion="Use --message '<text>' to provide a commit message non-interactively.",
        )
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
    if not sys.stdin.isatty():
        _die(
            "No TTY available for editor.",
            suggestion="Use --content '<text>' or pipe input to provide content non-interactively.",
        )
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(initial)
        f.flush()
        subprocess.call([editor, f.name])
        return Path(f.name).read_text()


# ── Shared CLI patterns ───────────────────────────────────────────────────


def _empty_state(message: str) -> None:
    """Print a muted empty-state message."""
    console.print(f"[muted]{message}[/]")


def _output_result(args, result: dict, success_msg: str) -> None:
    """Output a command result as JSON or a styled success message.

    Replaces the repeated ``if args.json: _json_out(result); else: _ok(...)``
    pattern that appears in 8+ handlers.
    """
    if getattr(args, "json", False):
        _json_out(result)
    else:
        _ok(success_msg)


def _resolve_author_names(db, author_ids: list[str]) -> list[str]:
    """Convert author UUIDs to display names for human-readable output.

    UUIDs that can't be resolved are shown as 8-char prefixes.
    """
    if not author_ids:
        return []
    users = {u.id: u for u in get_users_by_ids(db, set(author_ids))}
    return [users[uid].name if uid in users else uid[:8] for uid in author_ids]


def _require_resolved_article(db, args_id: str, *, check_integrity: bool = True):
    """Resolve an article by ref, assert integrity, return (article, article_id).

    Replaces the repeated triplet of ``_resolve_article_id`` +
    ``article_id = article.id`` + ``assert_article_integrity``.
    """
    article = _resolve_article_id(db, args_id)
    if check_integrity:
        assert_article_integrity(db, article.id)
    return article, article.id
