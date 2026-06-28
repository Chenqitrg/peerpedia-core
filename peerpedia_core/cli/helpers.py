# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Shared infrastructure for CLI handlers — DB, editor, session, user resolution.

Layer 1 of the CLI package.  Imports from ``display`` (Layer 0),
``output`` (Layer 1), and ``core/`` (external).  Does NOT import from
handlers or parser.
"""

from __future__ import annotations

import functools
import getpass
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from peerpedia_core.cli.display import console
from peerpedia_core.core import (
    reconcile_integrity, count_articles, count_unread_notifications,
    db_repl_setup, db_session, find_users, get_article,
    get_head_hash, get_notifications_for_user,
    get_reviews_for_article, get_top_users_by_followers,
    get_user, list_users_by_name, list_users_by_ids, list_articles, list_users,
    resolve_username_or_alias, search_articles,
)
# Re-export for REPL (arch rule: repl/ only imports from cli/).
# These are pure search functions — no _die, no exit.
__all_helpers__ = ["find_users", "search_articles", "list_articles"]
from peerpedia_core.config.paths import ARTICLES_DIR as DEFAULT_ARTICLES_DIR, DB_PATH, DB_URL, SESSION_FILE
from peerpedia_core.crypto import load_private_key, _public_key_to_bytes
from peerpedia_core.exceptions import PeerpediaError, TransportError
from peerpedia_core.types import short_id
from peerpedia_core.types.scores import SCORE_DIMENSIONS

# Output functions — extracted to cli/output.py to break circular dependency.
# Re-exported so existing handler imports continue to work.
from peerpedia_core.cli.output import (
    _die, _die_json_mode, _empty_state, _json_out, _log, _ok, _open_file,
    _out, _out_error_raw, _output_result, _page, _set_die_json_mode, _show,
)

_data_dir_ready = False


def _get_password(args, confirm: bool = False) -> str:
    """Read password from --password, env, or TTY prompt."""
    pw = getattr(args, "password", None) or os.environ.get("PEERPEDIA_PASSWORD")
    if pw:
        return pw
    if not sys.stdin.isatty():
        _out(None, "NO_TTY")
    password = getpass.getpass("Password: ")
    if not password:
        _out(None, "EMPTY_PASSWORD")
    if confirm:
        again = getpass.getpass("Confirm password: ")
        if password != again:
            _out(None, "PASSWORD_MISMATCH")
    return password


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
        _set_die_json_mode(getattr(args, "json", False))
        try:
            with db_session(DB_URL) as db:
                return func(db, args)
        except PeerpediaError as e:
            # Expected business-logic error — preserve type information.
            _die(str(e.detail), code=e.code, **e.context)
        except Exception as e:
            if _die_json_mode.get():
                import traceback
                _die(str(e), code="INTERNAL_ERROR",
                     traceback=traceback.format_exc())
            else:
                import traceback
                traceback.print_exc()
                _die(str(e), code="INTERNAL_ERROR")
        finally:
            _set_die_json_mode(False)

    return wrapper


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
        from peerpedia_core.core.sync_article import pull_new_article
        from peerpedia_core.cli.bundle_utils import _TRANSPORT
        try:
            pull_new_article(db, _TRANSPORT, server, article_id)
        except TransportError:
            pass  # best-effort: server unreachable, fall through to die
        # Retry after pull
        for ext in [".md", ".typ"]:
            f = rp / f"article{ext}"
            if f.exists():
                return f

    _out(None, "SOURCE_NOT_FOUND", article_id=article_id)


def _resolve_and_display_article(db, article, *, author_ids: list[str] | None = None) -> None:
    """Backward-compat — delegates to ``display.display_article_meta``."""
    from peerpedia_core.cli.display import display_article_meta
    display_article_meta(db, article, author_ids=author_ids)


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
    _out(None, "USER_NOT_REGISTERED")


def _resolve_user_by_atname(db, name: str) -> str:
    """Resolve ``@name`` → user ID via username/alias lookup.

    Returns the user ID on exact match.  Calls ``_die`` only when zero or
    multiple users match — both are terminal for one-shot CLI commands.
    In the REPL this function is NOT used; REPL calls
    ``resolve_username_or_alias`` directly and handles ambiguity interactively.
    """
    session_user = _get_session_user()
    users = resolve_username_or_alias(db, session_user, name)

    if len(users) == 1:
        return users[0].id
    if len(users) > 1:
        candidates = "\n".join(f"  {u.id}  {u.name}" for u in users)
        _out(None, "AMBIGUOUS_NAME", name=f"@{name}", ids=candidates)
    _out(None, "USER_NOT_FOUND", name=f"@{name}")


# FIXME: _resolve_user wraps find_users with _die — REPL can't use this.
# Callers that need a single user should use get_user (exact) or handle
# list results from search_users themselves.
def _resolve_user(db, user_ref: str) -> str:
    """Resolve a user reference to a user ID.

    ``@name`` → username/alias lookup.
    Plain string → delegates to ``commands.find_users`` (UUID → prefix → name).

    Terminal for CLI callers: zero or multiple matches call ``_die``.
    """
    if user_ref.startswith("@"):
        return _resolve_user_by_atname(db, user_ref[1:])

    results = find_users(db, user_ref)
    if len(results) == 1:
        return results[0].id
    if len(results) > 1:
        names = ", ".join(f"{short_id(u.id)} ({u.name})" for u in results)
        _out(None, "AMBIGUOUS_NAME", name=user_ref, ids=names)
        return ""  # unreachable
    _out(None, "USER_NOT_FOUND", name=user_ref)


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
    _valid_abbr = set(SCORE_DIMENSIONS.keys())
    _valid_full = set(SCORE_DIMENSIONS.values())
    _valid = _valid_abbr | _valid_full
    result = {}
    for part in scores_str.split(","):
        part = part.strip()
        if not part:
            continue
        k, v = _parse_score_part(part, _valid, _valid_abbr)
        result[k] = v
    return result


def _parse_score_part(part: str, valid_keys: set[str], valid_abbr: set[str]) -> tuple[str, int]:
    """Parse one ``key=value`` score part.  Dies with BAD_REQUEST on invalid input."""
    if "=" not in part:
        _out(None, "SCORE_MALFORMED", part=part)
    k, v = part.split("=", 1)
    k, v = k.strip(), v.strip()
    if k not in valid_keys:
        abbr_list = ", ".join(sorted(valid_abbr))
        _out(None, "SCORE_UNKNOWN_DIM", key=k, valid=abbr_list)
    # Normalize abbreviations to full names (downstream code expects full names).
    if k in valid_abbr:
        k = SCORE_DIMENSIONS[k]
    try:
        score = int(v)
    except ValueError:
        _out(None, "SCORE_NOT_INT", key=k, value=v)
    if not 1 <= score <= 5:
        _out(None, "SCORE_OUT_OF_RANGE", key=k, value=str(score))
    return k, score


def _prompt_commit_message(diff: str = "") -> str:
    """Open ``$EDITOR`` to get a commit message, like ``git commit``.

    Shows a template with the diff below ``#`` comment lines so the
    user can review what changed before writing the message.
    Empty messages are rejected.
    """
    if not sys.stdin.isatty():
        _out(None, "NO_TTY_EDITOR")
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
        _out(None, "EMPTY_COMMIT_MSG")
    return msg


def _open_editor(initial: str) -> str:
    """Open $EDITOR (defaults to vim) and return the edited text.

    Users set their preferred editor via the EDITOR environment variable:
      export EDITOR=nano    # add to ~/.zshrc or ~/.bashrc
      EDITOR=code peerpedia article create --title "Hello"  # one-off
    """
    if not sys.stdin.isatty():
        _out(None, "NO_TTY_EDITOR")
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(initial)
        f.flush()
        subprocess.call([editor, f.name])
        return Path(f.name).read_text()


def _resolve_author_names(db, author_ids: list[str]) -> list[str]:
    """Convert author UUIDs to display names for human-readable output.

    UUIDs that can't be resolved are shown as 8-char prefixes.
    """
    if not author_ids:
        return []
    users = {u.id: u for u in list_users_by_ids(db, set(author_ids))}
    return [users[uid].name if uid in users else short_id(uid) for uid in author_ids]


# FIXME: should use get_article (exact) for the "require exactly one" case,
# not search_articles.  Multiple matches from search are normal — the
# problem is using the wrong function, not having too many results.
def _require_resolved_article(db, args_id: str, *, check_integrity: bool = True):
    """Search articles by *args_id* and require exactly one match.

    Zero or multiple matches call ``_die`` (CLI can't pick interactively).
    """
    results = search_articles(db, args_id)
    if len(results) == 1:
        article = results[0]
        if check_integrity:
            reconcile_integrity(db, article.id)
        return article, article.id
    if len(results) > 1:
        names = ", ".join(f"{short_id(a.id)} ({a.title})" for a in results)
        _out(None, "ARTICLE_MULTIPLE", query=args_id, ids=names)
    _out(None, "ARTICLE_NOT_FOUND", article_id=args_id)
