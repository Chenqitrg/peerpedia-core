# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Argument parser — maps CLI commands to handler functions.

Defined declaratively as a ``COMMANDS`` table so ``build_parser`` is a
single loop rather than 180 lines of copy-paste argparse registration.
"""

from __future__ import annotations

import argparse

from peerpedia_core.cli.handlers import (
    _cmd_article_create, _cmd_article_delete, _cmd_article_edit,
    _cmd_article_list,
    _cmd_article_publish, _cmd_article_scan,
    _cmd_article_show,
    _cmd_bookmark_add, _cmd_bookmark_remove,
    _cmd_follow_user, _cmd_unfollow_user,
    _cmd_compile,
    _cmd_fork,
    _cmd_account_search,
    _cmd_login,
    _cmd_maintainer_add, _cmd_maintainer_list, _cmd_maintainer_remove,
    _cmd_merge_accept, _cmd_merge_propose,
    _cmd_mother,
    _cmd_register,
    _cmd_review_list, _cmd_review_submit,
    _cmd_sync_push, _cmd_sync_status,
    _cmd_whoami,
)

from peerpedia_core.types.scores import SCORE_FORMAT_EXAMPLE

# ═══════════════════════════════════════════════════════════════════════════════
# Argument spec helpers
# ═══════════════════════════════════════════════════════════════════════════════

_COMMON_ARGS = [
    (("--json",), {"action": "store_true", "help": "Output as JSON"}),
]


def _add_args(p: argparse.ArgumentParser, *arg_specs: list) -> None:
    """Register arguments from specs like ``(("--name",), {"required": True})``."""
    for args, kwargs in arg_specs:
        p.add_argument(*args, **kwargs)


def _add_common(p: argparse.ArgumentParser) -> None:
    _add_args(p, *_COMMON_ARGS)


# ═══════════════════════════════════════════════════════════════════════════════
# Command table (declarative — edit this, not build_parser)
# ═══════════════════════════════════════════════════════════════════════════════

# Each group: (name, help, [(sub_name, handler, [(args...)])])
# If a command has no subcommands, use an empty sub_name.
COMMAND_GROUPS = [
    ("account", "Account management", [
        ("register", _cmd_register, [
            (("--name",), {"required": True, "help": "Your display name"}),
            (("--json",), {"action": "store_true", "help": "Output as JSON"}),
        ]),
        ("login", _cmd_login, [
            (("--name",), {"required": True, "help": "Your display name"}),
            (("--json",), {"action": "store_true", "help": "Output as JSON"}),
        ]),
        ("whoami", _cmd_whoami, [
            (("--json",), {"action": "store_true", "help": "Output as JSON"}),
        ]),
        ("search", _cmd_account_search, [
            (("query",), {"help": "Search query (partial name, case-insensitive)"}),
            (("--json",), {"action": "store_true", "help": "Output as JSON"}),
        ]),
    ]),
    ("article", "Article management", [
        ("create", _cmd_article_create, [
            (("--title",), {"required": True, "help": "Article title"}),
            (("--format",), {"default": "markdown", "choices": ["markdown", "typst"],
                             "help": "Source format"}),
            (("--content",), {"help": "Article body (inline; omit to open editor)"}),
            (("--no-editor",), {"action": "store_true", "help": "Create empty article without opening editor"}),
            (("--publish",), {"action": "store_true", "help": "Publish immediately after creation"}),
            (("--scores",), {"help": f'Self-review scores, e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
        ]),
        ("show", _cmd_article_show, [
            (("id",), {"help": "Article ID (or prefix)"}),
            (("--show",), {"choices": ["meta", "full"], "default": "meta",
                           "help": "Display: meta (default), full (+content)"}),
        ]),
        ("list", _cmd_article_list, [
            (("--search",), {"help": "Fuzzy title search (case-insensitive)"}),
            (("--status",), {"choices": ["draft", "sedimentation", "published"],
                             "help": "Filter by status"}),
            (("--feed",), {"action": "store_true", "help": "Articles from followed users"}),
            (("--mine",), {"action": "store_true", "help": "My articles"}),
            (("--bookmarked",), {"action": "store_true", "help": "My bookmarked articles"}),
        ]),
        # TODO(review-feed): ``article reviewable`` — list sedimentation articles
        # from my 1-hop social circle that I haven't reviewed yet.
        ("edit", _cmd_article_edit, [
            (("id",), {"help": "Article ID (or prefix)"}),
            (("--content",), {"help": "New article body (omit to open editor)"}),
            (("--title",), {"help": "New article title"}),
            (("--no-editor",), {"action": "store_true", "help": "Skip editor; only apply --title if given"}),
        ]),
        ("publish", _cmd_article_publish, [
            (("id",), {"help": "Article ID (or prefix)"}),
            (("--scores",), {"required": True,
                             "help": f'Self-review scores, e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
        ]),
        ("delete", _cmd_article_delete, [
            (("id",), {"help": "Article ID (or prefix)"}),
        ]),
        ("scan", _cmd_article_scan, []),
    ]),
    ("review", None, [
        ("submit", _cmd_review_submit, [
            (("article_id",), {"help": "Article ID (or prefix)"}),
            (("--scores",), {"required": True,
                             "help": f'Five-dim scores, e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
            (("--comment",), {"help": "Optional review comment"}),
        ]),
        ("list", _cmd_review_list, [
            (("article_id",), {"help": "Article ID (or prefix)"}),
            (("--show",), {"choices": ["meta", "full"], "default": "meta",
                           "help": "Display: meta (scores, default) or full (scores + threads)"}),
        ]),
    ]),
    ("merge", None, [
        ("propose", _cmd_merge_propose, [
            (("fork_id",), {"help": "Your fork's article ID"}),
            (("--target",), {"required": True, "help": "Original article ID to merge into"}),
        ]),
        ("accept", _cmd_merge_accept, [
            (("proposal_id",), {"help": "Merge proposal ID"}),
            (("--target",), {"required": True, "help": "Target article ID"}),
        ]),
    ]),
    ("bookmark", None, [
        ("add", _cmd_bookmark_add, [
            (("article_id",), {"help": "Article ID (or prefix)"}),
        ]),
        ("remove", _cmd_bookmark_remove, [
            (("article_id",), {"help": "Article ID (or prefix)"}),
        ]),
    ]),
    ("sync", None, [
        ("status", _cmd_sync_status, [
            (("--server",), {"help": "Peer server URL (or set PEERPEDIA_SERVER env var)"}),
        ]),
        ("push", _cmd_sync_push, [
            (("--server",), {"help": "Peer server URL (or set PEERPEDIA_SERVER env var)"}),
        ]),
        # TODO(sync-pull): ``sync pull`` — git bundle pull (articles + reviews).
        # TODO(social-graph): ``sync discover`` — P2P social graph discovery.
        # TODO(social-graph): ``sync follow`` / ``sync unfollow`` — P2P follows.
        # TODO(social-graph): ``sync bookmarks`` — P2P bookmark sync.
    ]),
    ("maintainer", None, [
        ("add", _cmd_maintainer_add, [
            (("article_id",), {"help": "Article ID"}),
            (("--target-user",), {"required": True, "help": "User ID to add as maintainer"}),
        ]),
        ("remove", _cmd_maintainer_remove, [
            (("article_id",), {"help": "Article ID"}),
            (("--target-user",), {"required": True, "help": "User ID to remove from maintainers"}),
        ]),
        ("list", _cmd_maintainer_list, [
            (("article_id",), {"help": "Article ID"}),
        ]),
    ]),
]

# Top-level commands (no subparsers — just a single handler)
TOP_LEVEL = [
    ("fork", _cmd_fork, [
        (("article_id",), {"help": "Published article ID to fork"}),
    ]),
    ("compile", _cmd_compile, [
        (("id",), {"help": "Article ID (or prefix)"}),
        (("--format",), {"choices": ["pdf", "svg", "png", "html"],
                         "help": "Output format (default: pdf)"}),
    ]),
    ("follow", _cmd_follow_user, [
        (("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
    ]),
    ("unfollow", _cmd_unfollow_user, [
        (("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
    ]),
    ("?Mother", _cmd_mother, []),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_parser() -> argparse.ArgumentParser:
    # TODO(version): ``--version`` flag — print version + exit.
    # TODO(release): README + install guide — currently zero onboarding docs.
    # TODO(release): pip install smoke test — verify deps are declared correctly.
    # TODO(release): data migration — schema evolves, need upgrade path for users.
    # TODO(ux-onboarding): first-run wizard — register + create first article flow.
    # TODO(ux-onboarding): group commands in --help (Account / Article / Review).
    parser = argparse.ArgumentParser(
        "peerpedia", description="PeerPedia — peer review from the terminal",
    )
    subs = parser.add_subparsers(dest="command")

    # Nested command groups (e.g. ``peerpedia article create``)
    for name, help_text, subcommands in COMMAND_GROUPS:
        grp = subs.add_parser(name, help=help_text)
        grp_subs = grp.add_subparsers(dest="subcommand")
        for sub_name, handler, arg_specs in subcommands:
            p = grp_subs.add_parser(sub_name, help=_first_line(handler))
            _add_args(p, *arg_specs)
            _add_common(p)
            p.set_defaults(func=handler)

    # Top-level commands (e.g. ``peerpedia fork``)
    for name, handler, arg_specs in TOP_LEVEL:
        p = subs.add_parser(name, help=_first_line(handler))
        _add_args(p, *arg_specs)
        _add_common(p)
        p.set_defaults(func=handler)

    return parser


def _first_line(func) -> str:
    """Extract the first line of a handler's docstring for argparse help."""
    return (func.__doc__ or "").splitlines()[0].strip()


def get_cmd_map() -> dict[str, list[str]]:
    """Return ``{flat_cmd: [group, subcmd]}`` for the REPL dispatcher.

    Flat commands like ``"create"`` map to argparse groups like
    ``["article", "create"]`` so the REPL can build the full argv.
    """
    result: dict[str, list[str]] = {}
    for name, _help, subcommands in COMMAND_GROUPS:
        for sub_name, _handler, _args in subcommands:
            result[sub_name] = [name, sub_name]
    for name, _handler, _args in TOP_LEVEL:
        result[name] = [name]
    return result
