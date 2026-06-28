# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Command dispatch — lazy-load handlers by ``command_id``.

Parser sets ``args.command_id`` and ``args.func = dispatch``.  Dispatch
looks up the command ID, imports the handler module on first call, and
runs the handler with the parsed args.

This keeps ``parser.py`` free of handler imports — importing the parser
no longer pulls in sync, transport, storage, or server.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable

# command_id → (module_path, function_name)
_HANDLER_MAP: dict[str, tuple[str, str]] = {
    # ── Account ──
    "account.register":  ("peerpedia_core.cli.handlers.register",  "_cmd_register"),
    "account.login":     ("peerpedia_core.cli.handlers.login",     "_cmd_login"),
    "account.recover":   ("peerpedia_core.cli.handlers.login",     "_cmd_recover"),
    "account.whoami":    ("peerpedia_core.cli.handlers.account",   "_cmd_whoami"),
    "account.bootstrap": ("peerpedia_core.cli.handlers.bootstrap", "_cmd_bootstrap"),
    "account.delete":    ("peerpedia_core.cli.handlers.account",   "_cmd_account_delete"),
    "account.search":    ("peerpedia_core.cli.handlers.account",   "_cmd_account_search"),
    # ── Article ──
    "article.create":  ("peerpedia_core.cli.handlers.create",  "_cmd_article_create"),
    "article.show":    ("peerpedia_core.cli.handlers.read",    "_cmd_article_show"),
    "article.list":    ("peerpedia_core.cli.handlers.read",    "_cmd_article_list"),
    "article.edit":    ("peerpedia_core.cli.handlers.edit",    "_cmd_article_edit"),
    "article.publish": ("peerpedia_core.cli.handlers.edit",    "_cmd_article_publish"),
    "article.delete":  ("peerpedia_core.cli.handlers.edit",    "_cmd_article_delete"),
    "article.scan":    ("peerpedia_core.cli.handlers.edit",    "_cmd_article_scan"),
    "article.diff":    ("peerpedia_core.cli.handlers.edit",    "_cmd_article_diff"),
    # ── Review ──
    "review.submit":  ("peerpedia_core.cli.handlers.reviews", "_cmd_review_submit"),
    "review.list":    ("peerpedia_core.cli.handlers.reviews", "_cmd_review_list"),
    "review.reply":   ("peerpedia_core.cli.handlers.reviews", "_cmd_review_reply"),
    "review.invite":  ("peerpedia_core.cli.handlers.reviews", "_cmd_review_invite"),
    "review.accept":  ("peerpedia_core.cli.handlers.reviews", "_cmd_review_accept"),
    "review.decline": ("peerpedia_core.cli.handlers.reviews", "_cmd_review_decline"),
    "review.rate":    ("peerpedia_core.cli.handlers.reviews", "_cmd_review_rate"),
    # ── Merge ──
    "merge.propose":  ("peerpedia_core.cli.handlers.fork", "_cmd_merge_propose"),
    "merge.accept":   ("peerpedia_core.cli.handlers.fork", "_cmd_merge_accept"),
    "merge.withdraw": ("peerpedia_core.cli.handlers.fork", "_cmd_merge_withdraw"),
    # ── Alias ──
    "alias.set":    ("peerpedia_core.cli.handlers.alias", "_cmd_alias_set"),
    "alias.remove": ("peerpedia_core.cli.handlers.alias", "_cmd_alias_remove"),
    "alias.list":   ("peerpedia_core.cli.handlers.alias", "_cmd_alias_list"),
    # ── Share ──
    "share.add":    ("peerpedia_core.cli.handlers.share", "_cmd_share_add"),
    "share.list":   ("peerpedia_core.cli.handlers.share", "_cmd_share_list"),
    "share.remove": ("peerpedia_core.cli.handlers.share", "_cmd_share_remove"),
    # ── Bookmark ──
    "bookmark.add":    ("peerpedia_core.cli.handlers.bookmark", "_cmd_bookmark_add"),
    "bookmark.remove": ("peerpedia_core.cli.handlers.bookmark", "_cmd_bookmark_remove"),
    # ── Social ──
    "follow":    ("peerpedia_core.cli.handlers.social", "_cmd_follow_user"),
    "unfollow":  ("peerpedia_core.cli.handlers.social", "_cmd_unfollow_user"),
    "following": ("peerpedia_core.cli.handlers.social", "_cmd_following"),
    "followers": ("peerpedia_core.cli.handlers.social", "_cmd_followers"),
    # ── School ──
    "school": ("peerpedia_core.cli.handlers.school", "_cmd_school"),
    # ── Server ──
    "server.start": ("peerpedia_core.cli.handlers.server", "_cmd_server_start"),
    # ── Sync ──
    "sync.status":   ("peerpedia_core.cli.handlers.bundle", "_cmd_sync_status"),
    "sync.pull":     ("peerpedia_core.cli.handlers.bundle", "_cmd_sync_pull"),
    "sync.discover": ("peerpedia_core.cli.handlers.bundle", "_cmd_sync_discover"),
    # ── Notifications ──
    "notifications":      ("peerpedia_core.cli.handlers.notifications", "_cmd_notifications"),
    "notifications.read": ("peerpedia_core.cli.handlers.notifications", "_cmd_notification_read"),
    # ── Maintainer ──
    "maintainer.add":     ("peerpedia_core.cli.handlers.maintainers", "_cmd_maintainer_add"),
    "maintainer.remove":  ("peerpedia_core.cli.handlers.maintainers", "_cmd_maintainer_remove"),
    "maintainer.list":    ("peerpedia_core.cli.handlers.maintainers", "_cmd_maintainer_list"),
    "maintainer.consent": ("peerpedia_core.cli.handlers.maintainers", "_cmd_maintainer_consent"),
    "maintainer.revoke":  ("peerpedia_core.cli.handlers.maintainers", "_cmd_maintainer_revoke"),
    # ── Top-level ──
    "schema":  ("peerpedia_core.cli.handlers.schema", "_cmd_schema"),
    "fork":    ("peerpedia_core.cli.handlers.fork",   "_cmd_fork"),
    "compile": ("peerpedia_core.cli.handlers.compile_", "_cmd_compile"),
    "mother":  ("peerpedia_core.cli.handlers.mother", "_cmd_mother"),
    "help":    ("peerpedia_core.cli.handlers.help",   "_cmd_meta_help"),
}

_cache: dict[str, Callable] = {}


def dispatch(args) -> None:
    """Look up ``args.command_id``, lazy-load the handler, and run it."""
    cmd_id: str = getattr(args, "command_id", "")
    if not cmd_id:
        return  # parser fallback — help already displayed

    if cmd_id not in _cache:
        module_path, func_name = _HANDLER_MAP[cmd_id]
        mod = importlib.import_module(module_path)
        _cache[cmd_id] = getattr(mod, func_name)

    handler = _cache[cmd_id]
    handler(args)


def get_cmd_map_for_parser() -> dict[str, list[str]]:
    """Return ``{flat_cmd: [group, subcmd]}`` for the REPL dispatcher.

    Derives from ``_HANDLER_MAP`` so there is a single source of truth.
    """
    from collections import defaultdict

    result: dict[str, list[str]] = {}
    sub_name_groups: dict[str, list[str]] = defaultdict(list)

    # First pass: collect which groups share each sub-name
    for cmd_id in _HANDLER_MAP:
        parts = cmd_id.split(".")
        if len(parts) == 2:
            sub_name_groups[parts[1]].append(parts[0])

    # Second pass: register compound + short names
    for cmd_id in _HANDLER_MAP:
        parts = cmd_id.split(".")
        if len(parts) == 2:
            group, sub = parts[0], parts[1]
            result[cmd_id.replace(".", " ")] = [group, sub]
            if sub_name_groups[sub][0] == group:
                result[sub] = [group, sub]
        elif len(parts) == 1:
            result[parts[0]] = [parts[0]]

    return result
