# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Structured user-facing messages — single ``_out()`` entry point.

Every message knows its own kind, so callers just pass a code::

    _out("REGISTERED", data={"id": uid}, name="Alice")     # success → _show
    _out("AUTH_FAILED")                                     # error   → _die
    _out("L_SYNC_FAILED", server=srv, error=e)             # log     → _log.warning

``data`` is only meaningful for success messages (included in JSON output).
Error and log messages ignore it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto

_log = logging.getLogger(__name__)


class Kind(Enum):
    SUCCESS = auto()  # _out — JSON or pretty, then exit 0
    ERROR = auto()    # _out — JSON or pretty, then exit 1
    NOTIFY = auto()   # _out — JSON skip, pretty print, continue
    WARNING = auto()  # _log.warning
    INFO = auto()     # _log.info


@dataclass(frozen=True)
class _Msg:
    text: str
    kind: Kind = Kind.SUCCESS
    suggestion: str = ""
    see_also: tuple[str, ...] = ()
    log_text: str = ""  # override for logging (no Rich markup)


# ═══════════════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════════════

_REGISTRY: dict[str, _Msg] = {
    # ── Success ──────────────────────────────────────────────────────────
    "OK": _Msg("✓ {msg}"),
    "REGISTERED": _Msg("Registered [accent]{name}[/] ({id_short})"),
    "LOGGED_IN": _Msg("Logged in as [accent]{name}[/] ({id_short})"),
    "RECOVERED": _Msg("Recovered key for [accent]{name}[/] ({id_short})"),
    "BOOTSTRAPPED": _Msg("Bootstrapped user [accent]{name}[/] ({id_short})\n"
        "Now run: [accent]peerpedia account recover --user-id {id_short}[/]"),
    "ACCOUNT_DELETED": _Msg("Account [accent]{name}[/] deleted. Goodbye."),
    "NOT_LOGGED_IN": _Msg("[muted]Not logged in. Use register or login.[/]"),
    "ARTICLE_CREATED": _Msg("[dim]Created [accent]{id_short}[/] \"{title}\" (draft)[/]"),
    "ARTICLE_UPDATED": _Msg("Updated [accent]{id_short}[/] — {title}"),
    "ARTICLE_PUBLISHED": _Msg("Published [accent]{id_short}[/] to sedimentation pool"),
    "ARTICLE_DELETED": _Msg("Deleted [accent]{id_short}[/]"),
    "ARTICLE_SCANNED": _Msg("Scan complete — [accent]{count}[/] article(s) auto-published"),
    "ARTICLE_SCANNED_EMPTY": _Msg("[muted]Scan complete — 0 articles ready for publish.[/]"),
    "FOLLOWING": _Msg("Now following [accent]{name}[/]"),
    "FOLLOWING_COUNT": _Msg("Following {count} user(s)"),
    "FOLLOWERS_COUNT": _Msg("Followers {count} user(s)"),
    "UNFOLLOWED": _Msg("Stopped following [accent]{name}[/]"),
    "FORKED": _Msg("Forked → [accent]{id_short}[/] ({title})"),
    "MERGE_PROPOSED": _Msg("Merge proposed [accent]{id_short}[/] → target {target_id}"),
    "MERGE_ACCEPTED": _Msg("Merge accepted — [accent]{id_short}[/]"),
    "MERGE_WITHDRAWN": _Msg("Proposal [accent]{id_short}[/] withdrawn"),
    "BOOKMARKED": _Msg("Bookmarked [accent]{name}[/]"),
    "BOOKMARK_REMOVED": _Msg("Removed bookmark for [accent]{id_short}[/]"),
    "SHARED": _Msg("Shared [accent]{name}[/]{to_str}"),
    "UNSHARED": _Msg("Unshared [accent]{name}[/]"),
    "ALIAS_SET": _Msg("Alias [accent]{alias}[/] → {target_id}"),
    "ALIAS_REMOVED": _Msg("Alias removed for {target_id}"),
    "REVIEW_SUBMITTED": _Msg("Review submitted"),
    "REVIEW_INVITED": _Msg("Invited [accent]{name}[/] to review {id_short}"),
    "INVITATION_ACCEPTED": _Msg("Invitation accepted"),
    "INVITATION_DECLINED": _Msg("Invitation declined"),
    "HELPFULNESS_RATED": _Msg("Helpfulness rated [accent]{score}[/]"),
    "W_REGISTER_SWITCH": _Msg("[warning]⚠ Already logged in as [accent]{name}[/] (id: {id_short}). "
        "Registering will switch to the new user.[/]",
        kind=Kind.NOTIFY),
    "W_NO_KNOWN_PEERS": _Msg("[dim]No known peers — auto-sync skipped. "
        "Set PEERPEDIA_SERVER or run 'sync discover'.[/]",
        kind=Kind.NOTIFY),
    "W_AUTO_SYNCING": _Msg("[dim]Auto-syncing with {count} peer(s)...[/]",
        kind=Kind.NOTIFY),
    "EMPTY_SEARCH": _Msg("[muted]No users match '{query}'.[/]", kind=Kind.NOTIFY),
    "EMPTY_REVIEWS": _Msg("[muted]No reviews yet.[/]", kind=Kind.NOTIFY),
    "EMPTY_NOTIFICATIONS": _Msg("[muted]No notifications.[/]", kind=Kind.NOTIFY),
    "EMPTY_ARTICLES": _Msg("[muted]No articles.[/]", kind=Kind.NOTIFY),

    # ── Errors ───────────────────────────────────────────────────────────
    "NOT_FOUND": _Msg("{what} not found or ambiguous.",
        kind=Kind.ERROR,
        suggestion="Check the identifier and try again.",
        see_also=("article list", "sync pull")),
    "ARTICLE_NOT_FOUND": _Msg("Article '{article_id}' not found or ambiguous.",
        kind=Kind.ERROR,
        suggestion="Check the article ID, or try 'peerpedia article list' to browse.",
        see_also=("article list", "sync pull")),
    "USER_NOT_FOUND": _Msg("User '{name}' not found.",
        kind=Kind.ERROR,
        suggestion="Check the spelling, or register first: "
                   "peerpedia account register --name <your-name>",
        see_also=("account register", "account search")),
    "USER_NOT_FOUND_LOCAL": _Msg("User '{user_id}' not found locally.",
        kind=Kind.ERROR,
        suggestion="Bootstrap first with: "
                   "peerpedia account bootstrap --from '<json>'",
        see_also=("account bootstrap",)),
    "USER_NOT_FOUND_PEER": _Msg("User '{name}' not found on {peer}.",
        kind=Kind.ERROR,
        suggestion="Check the --user-id or try a different peer server.",
        see_also=("account bootstrap",)),
    "BOOTSTRAP_FAILED": _Msg("Failed to bootstrap user {user_id} from {peer}.", kind=Kind.ERROR,
        suggestion="Verify the peer server is reachable and the user ID is correct."),
    "USER_ID_MISMATCH": _Msg("User ID '{user_id}' does not match any user named '{name}'.",
        kind=Kind.ERROR,
        suggestion="Check the --user-id or omit it to see all matches.",
        see_also=("account whoami",)),
    "AUTH_FAILED": _Msg("Wrong password.",
        kind=Kind.ERROR,
        suggestion="If you forgot: peerpedia account recover --name <name>. "
                   "If new device: bootstrap first.",
        see_also=("account recover", "account bootstrap")),
    "ACCOUNT_LOCKED": _Msg("Account locked — too many failed attempts. Try again in {minutes} minute(s).",
        kind=Kind.ERROR,
        suggestion="Wait for the lockout to expire, or use account recover.",
        see_also=("account recover",)),
    "UNAUTHORIZED": _Msg("Not logged in.",
        kind=Kind.ERROR, suggestion="Run 'peerpedia account login' first.",
        see_also=("account login", "account register")),
    "UNSUPPORTED_KEY": _Msg("User '{name}' was registered before key derivation was supported.",
        kind=Kind.ERROR,
        suggestion="Re-register: peerpedia account register --name {name}",
        see_also=("account register",)),
    "DUPLICATE_NAME": _Msg("A user named '{name}' already exists (ID: {ids}).",
        kind=Kind.ERROR,
        suggestion="Use 'account login --name <name>' to sign in, "
                   "or pick a different name.",
        see_also=("account login", "account whoami")),
    "DUPLICATE_USER_LOCAL": _Msg("User '{name}' (id: {id_short}) already exists in local DB.",
        kind=Kind.ERROR,
        suggestion="Use 'account login' if this is your account.",
        see_also=("account login",)),
    "AMBIGUOUS_NAME": _Msg("Multiple users named '{name}'.",
        kind=Kind.ERROR,
        suggestion="Use --user-id to specify which one: {ids}",
        see_also=("account whoami",)),
    "AMBIGUOUS_ARGS": _Msg("Specify either --name or --user-id.",
        kind=Kind.ERROR,
        suggestion="Use --name for display name, or --user-id for UUID.",
        see_also=("account whoami --verbose",)),
    "NO_TTY": _Msg("No TTY available for password input.",
        kind=Kind.ERROR,
        suggestion="Use --password '<pwd>' or set PEERPEDIA_PASSWORD env variable."),
    "EMPTY_PASSWORD": _Msg("Password must not be empty.",
        kind=Kind.ERROR),
    "PASSWORD_MISMATCH": _Msg("Passwords do not match.",
        kind=Kind.ERROR),
    "NO_CONTENT": _Msg("No --content and no terminal for editor.",
        kind=Kind.ERROR,
        suggestion="Use --content '<text>' or --no-editor for empty article.",
        see_also=("article create",)),
    "EMPTY_COMMIT_MSG": _Msg("Aborting: empty commit message.",
        kind=Kind.ERROR),
    "EMPTY_REPLY": _Msg("Aborting: empty reply.", kind=Kind.ERROR),
    "INVALID_JSON": _Msg("Invalid JSON: {error}", kind=Kind.ERROR,
        suggestion="Check the JSON syntax and try again."),
    "INVALID_BOOTSTRAP_FIELD": _Msg("Bootstrap JSON missing '{field}' field.", kind=Kind.ERROR,
        suggestion="Use 'account whoami --verbose --json' on the original device to get valid bootstrap data.",
        see_also=("account whoami --verbose",)),
    "INVALID_USER_ID": _Msg("Invalid user_id: {value!r} — must be a valid UUID.", kind=Kind.ERROR),
    "INVALID_PUBKEY": _Msg("Invalid public_key: not valid hex.",
        kind=Kind.ERROR),
    "INVALID_PUBKEY_LEN": _Msg("Invalid public_key length: {length} — must be 64 hex chars.", kind=Kind.ERROR),
    "INVALID_SALT": _Msg("Invalid salt: not valid hex.", kind=Kind.ERROR),
    "INVALID_SALT_LEN": _Msg("Invalid salt length: {length} — must be 32 hex chars.", kind=Kind.ERROR),
    "INVALID_SCORE": _Msg("Score for '{key}' must be 1-5, got {value}", kind=Kind.ERROR,
        suggestion="Valid dimensions: orig, rigor, comp, ped, imp. Example: --scores orig=4,rigor=3"),
    "COMPILE_FAILED": _Msg("Compilation failed: {error}",
        kind=Kind.ERROR,
        suggestion="Check the article source for syntax errors.",
        see_also=("article show --show full",)),
    "DIFF_INVALID_HASH": _Msg("{error}",
        kind=Kind.ERROR,
        suggestion="Valid commit refs: a full hash, a short prefix, HEAD, or ~N "
                   "(e.g. ~1 for the parent commit)."),
    "DIFF_REPO_MISSING": _Msg("{error}",
        kind=Kind.ERROR,
        suggestion="The article's git repository is missing. Try 'sync pull'.",
        see_also=("sync pull",)),
    "SCORE_MALFORMED": _Msg("Malformed score: '{part}' — expected key=value",
        kind=Kind.ERROR),
    "SCORE_UNKNOWN_DIM": _Msg("Unknown score dimension: '{key}'. Valid: {valid}",
        kind=Kind.ERROR),
    "SCORE_NOT_INT": _Msg("Score for '{key}' must be an integer, got '{value}'",
        kind=Kind.ERROR),
    "SCORE_OUT_OF_RANGE": _Msg("Score for '{key}' must be 1-5, got {value}",
        kind=Kind.ERROR),
    "NO_TTY_EDITOR": _Msg("No TTY available for editor.",
        kind=Kind.ERROR,
        suggestion="Use --content '<text>' or pipe input to provide content non-interactively."),
    "ARTICLE_MULTIPLE": _Msg("Multiple matches for '{query}': {ids}",
        kind=Kind.ERROR,
        suggestion="Use a longer prefix or the full UUID."),
    "REVIEW_DIR_ERROR": _Msg("DB has reviews but no reviews/ directory on disk for article {article_id}",
        kind=Kind.ERROR,
        suggestion="Try 'sync pull' to restore the git repository.",
        see_also=("sync pull",)),
    "OFFLINE": _Msg("Server {server} unreachable.",
        kind=Kind.ERROR,
        suggestion="Check: (1) server running? (2) PEERPEDIA_SERVER set? (3) network up?",
        see_also=("sync status",)),
    "NOT_CONFIGURED": _Msg("No peer server configured.",
        kind=Kind.ERROR,
        suggestion="Set PEERPEDIA_SERVER or pass --server."),
    "CONFIG_ERROR": _Msg("Cannot read default server from {path}: {error}", kind=Kind.ERROR),
    "SOURCE_NOT_FOUND": _Msg("No source file found for article {article_id}",
        kind=Kind.ERROR,
        suggestion="The article may have been discovered from a peer but its "
                   "content hasn't been downloaded yet. Try 'sync pull' first.",
        see_also=("sync pull",)),
    # ── Logging ──────────────────────────────────────────────────────────
    "L_AUTO_SYNC_ARTICLE": _Msg("",
        kind=Kind.WARNING,
        log_text="auto-sync article {article} to {server} failed: {error}"),
    "L_AUTO_SYNC_SERVER": _Msg("",
        kind=Kind.WARNING,
        log_text="auto-sync to {server} failed: {error}"),
    "L_AMBIGUOUS_INPUT": _Msg("",
        kind=Kind.WARNING,
        log_text="Both --name and --user-id given — using --user-id"),
    "L_DISCOVERED_PEERS": _Msg("",
        kind=Kind.INFO,
        log_text="Discovered {count} peer(s) from seed {seed}"),
    "L_SEED_UNREACHABLE": _Msg("",
        kind=Kind.INFO,
        log_text="Seed peer {seed} unreachable: {error}"),
    "L_REGISTERED_PEER": _Msg("",
        kind=Kind.INFO,
        log_text="Registered with peer {peer}"),
    "L_PEER_REG_FAILED": _Msg("",
        kind=Kind.WARNING,
        log_text="Peer registration to {peer} failed: {error}"),
}


def _lookup(code: str) -> tuple[str, _Msg]:
    """Return (code, msg) for *code*, or a generic fallback."""
    m = _REGISTRY.get(code)
    if m is None:
        return code, _Msg(code)
    return code, m


def _log_text(code: str, **fmt) -> str:
    """Return a plain-text formatted log message for *code*."""
    _, m = _lookup(code)
    template = m.log_text or m.text
    return template.format(**fmt) if fmt else template
