# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Argument parser — maps CLI commands to handler functions.

Defined declaratively as a ``COMMANDS`` table so ``build_parser`` is a
single loop rather than 180 lines of copy-paste argparse registration.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from peerpedia_core.cli.handlers import (
    _cmd_article_create, _cmd_article_delete, _cmd_article_diff, _cmd_article_edit,
    _cmd_article_list,
    _cmd_article_publish, _cmd_article_scan,
    _cmd_article_show,
    _cmd_alias_list, _cmd_alias_remove, _cmd_alias_set,
    _cmd_bookmark_add, _cmd_bookmark_remove,
    _cmd_follow_user, _cmd_followers, _cmd_following, _cmd_unfollow_user,
    _cmd_bootstrap,
    _cmd_compile,
    _cmd_fork,
    _cmd_account_delete,
    _cmd_account_search,
    _cmd_login,
    _cmd_recover,
    _cmd_maintainer_add, _cmd_maintainer_consent, _cmd_maintainer_list,
    _cmd_maintainer_remove, _cmd_maintainer_revoke,
    _cmd_merge_accept, _cmd_merge_propose, _cmd_merge_withdraw,
    _cmd_notifications, _cmd_notification_read,
    _cmd_share_add, _cmd_share_list, _cmd_share_remove,
    _cmd_mother,
    _cmd_register,
    _cmd_schema,
    _cmd_school,
    _cmd_meta_help,
    _cmd_review_accept, _cmd_review_decline, _cmd_review_invite, _cmd_review_list, _cmd_review_rate, _cmd_review_reply, _cmd_review_submit,
    _cmd_server_start,
    _cmd_sync_discover, _cmd_sync_pull, _cmd_sync_push, _cmd_sync_status,
    _cmd_whoami,
)

from peerpedia_core.types.scores import SCORE_FORMAT_EXAMPLE, _SCORE_DIMS_LIST

_HELP_DIR = Path(__file__).resolve().parent / "help"


def _load_help(name: str) -> str:
    """Load extended help text for a command from ``cli/help/<name>.txt``.

    Returns ``""`` if the file does not exist (extended help is optional).
    """
    path = _HELP_DIR / f"{name}.txt"
    if path.is_file():
        return path.read_text()
    return ""

# ═══════════════════════════════════════════════════════════════════════════════
# Argument spec helpers
# ═══════════════════════════════════════════════════════════════════════════════

_COMMON_ARGS = [
    (("--json",), {"action": "store_true", "help": "Output as JSON (explicit; default is JSON for AI consumption)"}),
    (("--rich",), {"action": "store_true", "help": "Output as human-readable Rich text"}),
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
            (("--password",), {"help": "Password (omit for interactive prompt; or set PEERPEDIA_PASSWORD env var)"}),
        ], {"epilog": _load_help("account_register")}),
        ("login", _cmd_login, [
            (("--name",), {"required": True, "help": "Your display name"}),
            (("--password",), {"help": "Password (omit for interactive prompt; or set PEERPEDIA_PASSWORD env var)"}),
            (("--peer",), {"help": "Peer server URL for remote bootstrap on a new device"}),
            (("--user-id",), {"help": "User UUID for remote bootstrap (needed on new devices)"}),
        ], {"epilog": _load_help("account_login")}),
        ("recover", _cmd_recover, [
            (("--name",), {"help": "Your display name"}),
            (("--user-id",), {"help": "Your user ID (UUID)"}),
        ], {"epilog": _load_help("account_recover")}),
        ("whoami", _cmd_whoami, [
            (("--verbose",), {"action": "store_true", "help": "Show user ID, public key, and salt for device bootstrap"}),
        ], {"epilog": _load_help("account_whoami")}),
        ("bootstrap", _cmd_bootstrap, [
            (("--from",), {"required": True, "dest": "from_", "metavar": "JSON",
             "help": "JSON blob from 'account whoami --verbose --json'"}),
            (("--peer",), {"help": "Peer URL for data sync after bootstrap"}),
        ], {"epilog": _load_help("account_bootstrap")}),
        ("delete", _cmd_account_delete, [
        ], {"epilog": _load_help("account_delete")}),
        ("search", _cmd_account_search, [
            (("query",), {"help": "Search query (partial name, case-insensitive)"}),
        ], {"epilog": _load_help("account_search")}),
    ]),
    ("article", "Article management", [
        ("create", _cmd_article_create, [
            (("--title",), {"required": True, "help": "Article title"}),
            (("--format",), {"default": "markdown", "choices": ["markdown", "typst"],
                             "help": "Source format"}),
            (("--content",), {"help": "Article body (inline; omit to open editor)"}),
            (("--no-editor",), {"action": "store_true", "help": "Create empty article without opening editor"}),
            (("--publish",), {"action": "store_true", "help": "Publish immediately after creation"}),
            (("--scores",), {"help": f'Self-review scores ({_SCORE_DIMS_LIST}), e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
        ], {"epilog": _load_help("article_create")}),
        ("show", _cmd_article_show, [
            (("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--show",), {"choices": ["meta", "full"], "default": "meta",
                           "help": "Display: meta (default), full (+content)"}),
        ], {"epilog": _load_help("article_show")}),
        ("list", _cmd_article_list, [
            (("--search",), {"help": "Fuzzy title search (case-insensitive)"}),
            (("--status",), {"choices": ["draft", "sedimentation", "published"],
                             "help": "Filter by status"}),
            (("--feed",), {"action": "store_true", "help": "Articles from followed users"}),
            (("--mine",), {"action": "store_true", "help": "My articles"}),
            (("--bookmarked",), {"action": "store_true", "help": "My bookmarked articles"}),
            (("--user",), {"help": "Show articles by this user (requires --server for remote fetch)"}),
            (("--server",), {"help": "Peer server URL for remote --user query"}),
        ], {"epilog": _load_help("article_list")}),
        ("edit", _cmd_article_edit, [
            (("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--content",), {"help": "New article body (omit to open editor)"}),
            (("--title",), {"help": "New article title"}),
            (("--no-editor",), {"action": "store_true", "help": "Skip editor; only apply --title if given"}),
        ], {"epilog": _load_help("article_edit")}),
        ("publish", _cmd_article_publish, [
            (("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--scores",), {"required": True,
                             "help": f'Self-review scores ({_SCORE_DIMS_LIST}), e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
        ], {"epilog": _load_help("article_publish")}),
        ("delete", _cmd_article_delete, [
            (("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--force",), {"action": "store_true", "help": "Delete without confirmation"}),
        ], {"epilog": _load_help("article_delete")}),
        ("scan", _cmd_article_scan, [], {"epilog": _load_help("article_scan")}),
        ("diff", _cmd_article_diff, [
            (("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("hash1",), {"help": "Old commit (hash, HEAD, or ~N)"}),
            (("hash2",), {"help": "New commit (hash, HEAD, or ~N)"}),
        ], {"epilog": _load_help("article_diff")}),
    ]),
    ("review", "Submit, invite, rate, and list peer reviews", [
        ("submit", _cmd_review_submit, [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--scores",), {"required": True,
                             "help": f'Five-dim scores ({_SCORE_DIMS_LIST}), e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
            (("--comment",), {"required": True, "help": "Review comment (min 200 characters)"}),
        ], {"epilog": _load_help("review_submit")}),
        ("list", _cmd_review_list, [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--show",), {"choices": ["meta", "full"], "default": "meta",
                           "help": "Display: meta (scores, default) or full (scores + threads)"}),
        ], {"epilog": _load_help("review_list")}),
        ("reply", _cmd_review_reply, [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--to",), {"required": True, "help": "Reviewer (@name, UUID, or prefix) to reply to"}),
        ], {"epilog": _load_help("review_reply")}),
        ("invite", _cmd_review_invite, [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--user",), {"required": True, "help": "User to invite (@name, UUID, or prefix)"}),
        ], {"epilog": _load_help("review_invite")}),
        ("accept", _cmd_review_accept, [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ], {"epilog": _load_help("review_accept")}),
        ("decline", _cmd_review_decline, [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ], {"epilog": _load_help("review_decline")}),
        ("rate", _cmd_review_rate, [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--reviewer",), {"required": True, "help": "Reviewer to rate (@name, UUID, or prefix)"}),
            (("--helpfulness",), {"required": True, "type": int, "choices": [1, 2, 3, 4, 5],
             "help": "Helpfulness score 1-5"}),
        ], {"epilog": _load_help("review_rate")}),
    ]),
    ("merge", "Propose, accept, or withdraw merge proposals", [
        ("propose", _cmd_merge_propose, [
            (("fork_id",), {"help": "Your fork's article ID"}),
            (("--target",), {"required": True, "help": "Original article ID to merge into"}),
        ], {"epilog": _load_help("merge_propose")}),
        ("accept", _cmd_merge_accept, [
            (("proposal_id",), {"help": "Merge proposal ID"}),
            (("--target",), {"required": True, "help": "Target article ID"}),
        ], {"epilog": _load_help("merge_accept")}),
        ("withdraw", _cmd_merge_withdraw, [
            (("proposal_id",), {"help": "Merge proposal ID to withdraw"}),
        ], {"epilog": _load_help("merge_withdraw")}),
    ]),
    ("alias", "Set or manage aliases for followed users", [
        ("set", _cmd_alias_set, [
            (("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
            (("alias",), {"help": "Alias to assign"}),
        ], {"epilog": _load_help("alias_set")}),
        ("remove", _cmd_alias_remove, [
            (("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
        ], {"epilog": _load_help("alias_remove")}),
        ("list", _cmd_alias_list, [], {"epilog": _load_help("alias_list")}),
    ]),
    ("share", "Share or recommend articles to followers", [
        ("add", _cmd_share_add, [
            (("article_id",), {"help": "Article ID to share"}),
            (("--to",), {"help": "Target user (@name, @alias, or UUID)"}),
            (("--comment",), {"help": "Optional comment on the share"}),
        ], {"epilog": _load_help("share_add")}),
        ("list", _cmd_share_list, [
            (("--mine",), {"action": "store_true", "help": "Show my shares instead of feed"}),
        ], {"epilog": _load_help("share_list")}),
        ("remove", _cmd_share_remove, [
            (("article_id",), {"help": "Article ID to unshare"}),
        ], {"epilog": _load_help("share_remove")}),
    ]),
    ("bookmark", "Bookmark articles for later reading", [
        ("add", _cmd_bookmark_add, [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ], {"epilog": _load_help("bookmark_add")}),
        ("remove", _cmd_bookmark_remove, [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ], {"epilog": _load_help("bookmark_remove")}),
    ]),
    ("following", "View who a user follows", [
        ("", _cmd_following, [
            (("--user",), {"required": True, "help": "User ID to query"}),
            (("--local",), {"action": "store_true", "help": "Read from local DB"}),
            (("--server",), {"help": "Peer server URL"}),
        ]),
    ]),
    ("followers", "View who follows a user", [
        ("", _cmd_followers, [
            (("--user",), {"required": True, "help": "User ID to query"}),
            (("--local",), {"action": "store_true", "help": "Read from local DB"}),
            (("--server",), {"help": "Peer server URL"}),
        ]),
    ]),
    ("server", "Run the PeerPedia server", [
        ("start", _cmd_server_start, [
            (("--host",), {"default": "127.0.0.1", "help": "Bind address"}),
            (("--port",), {"default": 8080, "type": int, "help": "Listen port"}),
            (("--public-url",), {"default": "", "help": "Public URL for peer registration (e.g. https://peer.example.com)"}),
        ], {"epilog": _load_help("server_start")}),
    ]),
    ("sync", "Push/pull articles to/from a peer server", [
        ("status", _cmd_sync_status, [
            (("--server",), {"help": "Peer server URL (or set PEERPEDIA_SERVER env var)"}),
        ], {"epilog": _load_help("sync_status")}),
        ("push", _cmd_sync_push, [
            (("--server",), {"help": "Peer server URL (or set PEERPEDIA_SERVER env var)"}),
        ], {"epilog": _load_help("sync_push")}),
        ("pull", _cmd_sync_pull, [
            (("--server",), {"help": "Peer server URL (or set PEERPEDIA_SERVER env var)"}),
        ], {"epilog": _load_help("sync_pull")}),
        ("discover", _cmd_sync_discover, [
            (("--depth",), {"type": int, "default": 1, "help": "Follow graph depth (default 1)"}),
            (("--max-users",), {"type": int, "default": 100, "help": "Max users to traverse"}),
        ], {"epilog": _load_help("sync_discover")}),
    ]),
    ("notifications", "View and manage notifications", [
        ("", _cmd_notifications, [
            (("--all",), {"action": "store_true", "help": "Show all notifications (not just unread)"}),
        ], {"epilog": _load_help("notifications")}),
        ("read", _cmd_notification_read, [
            (("notification_id",), {"help": "Notification ID to mark as read"}),
        ], {"epilog": _load_help("notifications_read")}),
    ]),
    ("maintainer", "Manage article co-authors (maintainers)", [
        ("add", _cmd_maintainer_add, [
            (("article_id",), {"help": "Article ID"}),
            (("--target-user",), {"required": True, "help": "User ID to add as maintainer"}),
        ], {"epilog": _load_help("maintainer_add")}),
        ("remove", _cmd_maintainer_remove, [
            (("article_id",), {"help": "Article ID"}),
            (("--target-user",), {"required": True, "help": "User ID to remove from maintainers"}),
        ], {"epilog": _load_help("maintainer_remove")}),
        ("list", _cmd_maintainer_list, [
            (("article_id",), {"help": "Article ID"}),
        ], {"epilog": _load_help("maintainer_list")}),
        ("consent", _cmd_maintainer_consent, [
            (("article_id",), {"help": "Article ID to consent to publish/merge"}),
        ], {"epilog": _load_help("maintainer_consent")}),
        ("revoke", _cmd_maintainer_revoke, [
            (("article_id",), {"help": "Article ID to revoke consent"}),
        ], {"epilog": _load_help("maintainer_revoke")}),
    ]),
]

# Top-level commands (no subparsers — just a single handler)
TOP_LEVEL = [
    ("schema", _cmd_schema, [
        (("command",), {"nargs": "?", "help": "Specific command name to describe"}),
    ]),
    ("fork", _cmd_fork, [
        (("article_id",), {"help": "Published article ID to fork"}),
    ], {"epilog": _load_help("fork")}),
    ("compile", _cmd_compile, [
        (("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        (("--format",), {"choices": ["pdf", "svg", "png", "html"],
                         "help": "Output format (default: pdf)"}),
    ], {"epilog": _load_help("compile")}),
    ("follow", _cmd_follow_user, [
        (("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
    ], {"epilog": _load_help("follow")}),
    ("unfollow", _cmd_unfollow_user, [
        (("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
    ], {"epilog": _load_help("unfollow")}),
    ("mother", _cmd_mother, []),
    ("school", _cmd_school, [
        (("--limit",), {"type": int, "default": 20, "help": "Max users to show"}),
        (("--server",), {"help": "Peer server URL (or set PEERPEDIA_SERVER env var)"}),
        (("--local",), {"action": "store_true", "help": "Read from local DB instead of peer server"}),
    ], {"epilog": _load_help("school")}),
    ("help", _cmd_meta_help, [
        (("topic",), {"nargs": "?", "help": "Command or topic to get help about (default: meta help)"}),
    ]),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all subcommands registered."""
    import importlib.metadata

    try:
        _version = importlib.metadata.version("peerpedia-core")
    except importlib.metadata.PackageNotFoundError:
        _version = "unknown"

    # Build friendlier command overview grouped by workflow
    _writing = ["article"]
    _reviewing = ["review"]
    _social = ["follow", "unfollow", "following", "followers", "school",
               "bookmark", "share", "alias"]
    _collab = ["merge", "fork", "maintainer"]
    _sync = ["sync", "server"]
    _other = ["account", "notifications", "compile", "schema", "help", "mother"]

    _all_grouped = [
        ("Writing & publishing", _writing),
        ("Peer review", _reviewing),
        ("Collaboration (fork, merge, co-authors)", _collab),
        ("Social & discovery", _social),
        ("Sync & networking", _sync),
        ("Account & utilities", _other),
    ]

    _lookup: dict[str, tuple[str, str, list[str]]] = {}
    for name, help_text, subcommands in COMMAND_GROUPS:
        subs = [s[0] for s in subcommands if s[0]]
        _lookup[name] = (name, help_text, subs)
    for entry in TOP_LEVEL:
        _lookup[entry[0]] = (entry[0], _first_line(entry[1]), [])

    _cmd_lines = []
    for section, cmds in _all_grouped:
        _cmd_lines.append(f"  {section}")
        for c in cmds:
            if c in _lookup:
                _name, _help, _subs = _lookup[c]
                if _subs:
                    _cmd_lines.append(f"    {_name:<14} {', '.join(_subs)}")
                else:
                    _cmd_lines.append(f"    {_name:<14} {_help}")
        _cmd_lines.append("")

    _examples = (
        "\nEXAMPLES — real tasks you can copy and paste\n\n"
        "  Your first paper:\n"
        "    peerpedia account register --name \"Albert Einstein\"\n"
        "    peerpedia article create --title \"On the Electrodynamics of Moving Bodies\"\n"
        "    peerpedia article publish abc12345 --scores \"orig=5,rigor=4,comp=4,ped=3,imp=5\"\n"
        "\n"
        "  Finding papers to read:\n"
        "    peerpedia article list                          # all public papers\n"
        "    peerpedia article list --search \"quantum\"       # papers about quantum topics\n"
        "    peerpedia article list --feed                    # papers from people you follow\n"
        "    peerpedia article show abc12345                  # read a paper's details\n"
        "    peerpedia article show abc12345 --show full      # read the full text\n"
        "\n"
        "  Improving your draft:\n"
        "    peerpedia article edit abc12345                  # open editor to revise\n"
        "    peerpedia article diff abc12345 ~1 HEAD          # see what changed last time\n"
        "\n"
        "  Peer reviewing:\n"
        "    peerpedia review submit abc12345 \\\n"
        "        --scores \"orig=4,rigor=3,comp=4,ped=3,imp=5\" \\\n"
        "        --comment \"This paper presents a novel approach to...\"\n"
        "    peerpedia review list abc12345                   # see all reviews of a paper\n"
        "\n"
        "  Working with others:\n"
        "    peerpedia account search Einstein                # find a colleague\n"
        "    peerpedia follow @einstein                       # follow their work\n"
        "    peerpedia maintainer add abc12345 --target-user @bob  # add a co-author\n"
        "    peerpedia fork abc12345                          # create your own copy to revise\n"
        "\n"
        "  Sharing with peers:\n"
        "    peerpedia sync push --server https://peer.example.com\n"
        "    peerpedia sync pull --server https://peer.example.com\n"
        "\n"
        "Add --help to any command for detailed options and more examples:\n"
        "    peerpedia article create --help\n"
        "    peerpedia review submit --help\n"
        "\n"
        "New to the command line?  Run:  peerpedia mother\n"
    )

    epilog = (
        "\nCOMMANDS\n"
        + "\n".join(_cmd_lines)
        + "\n"
        + _examples
    )

    parser = argparse.ArgumentParser(
        "peerpedia",
        description="PeerPedia — peer review from the terminal",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version}")
    subs = parser.add_subparsers(dest="command")

    # Nested command groups (e.g. ``peerpedia article create``)
    for name, help_text, subcommands in COMMAND_GROUPS:
        grp = subs.add_parser(name, help=help_text)
        grp_subs = grp.add_subparsers(dest="subcommand")
        for entry in subcommands:
            sub_name, handler, arg_specs = entry[0], entry[1], entry[2]
            extra = entry[3] if len(entry) > 3 else {}
            epilog = extra.get("epilog", "")
            if sub_name == "":
                # No subcommand — handler goes directly on the group parser
                _add_args(grp, *arg_specs)
                _add_common(grp)
                grp.set_defaults(func=handler)
            else:
                p = grp_subs.add_parser(
                    sub_name, help=_first_line(handler),
                    epilog=epilog,
                    formatter_class=argparse.RawDescriptionHelpFormatter,
                )
                _add_args(p, *arg_specs)
                _add_common(p)
                p.set_defaults(func=handler)

    # Top-level commands (e.g. ``peerpedia fork``)
    for entry in TOP_LEVEL:
        name, handler, arg_specs = entry[0], entry[1], entry[2]
        extra = entry[3] if len(entry) > 3 else {}
        epilog = extra.get("epilog", "")
        p = subs.add_parser(
            name, help=_first_line(handler),
            epilog=epilog,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
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
        for entry in subcommands:
            sub_name = entry[0]
            if sub_name:
                result[sub_name] = [name, sub_name]
    for entry in TOP_LEVEL:
        result[entry[0]] = [entry[0]]
    return result
