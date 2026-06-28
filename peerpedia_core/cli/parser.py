# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Argument parser — maps CLI commands to handler functions.

Defined declaratively as a ``COMMANDS`` table so ``build_parser`` is a
single loop rather than 180 lines of copy-paste argparse registration.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from peerpedia_core.cli.dispatch import dispatch

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
        ("register", "account.register", [
            (("--name",), {"required": True, "help": "Your display name"}),
            (("--password",), {"help": "Password (omit for interactive prompt; or set PEERPEDIA_PASSWORD env var)"}),
        ], {"epilog": _load_help("account_register")}),
        ("login", "account.login", [
            (("--name",), {"required": True, "help": "Your display name"}),
            (("--password",), {"help": "Password (omit for interactive prompt; or set PEERPEDIA_PASSWORD env var)"}),
            (("--peer",), {"help": "Peer server URL for remote bootstrap on a new device"}),
            (("--user-id",), {"help": "User UUID for remote bootstrap (needed on new devices)"}),
        ], {"epilog": _load_help("account_login")}),
        ("recover", "account.recover", [
            (("--name",), {"help": "Your display name"}),
            (("--user-id",), {"help": "Your user ID (UUID)"}),
        ], {"epilog": _load_help("account_recover")}),
        ("whoami", "account.whoami", [
            (("--verbose",), {"action": "store_true", "help": "Show user ID, public key, and salt for device bootstrap"}),
        ], {"epilog": _load_help("account_whoami")}),
        ("bootstrap", "account.bootstrap", [
            (("--from",), {"required": True, "dest": "from_", "metavar": "JSON",
             "help": "JSON blob from 'account whoami --verbose --json'"}),
            (("--peer",), {"help": "Peer URL for data sync after bootstrap"}),
        ], {"epilog": _load_help("account_bootstrap")}),
        ("delete", "account.delete", [
        ], {"epilog": _load_help("account_delete")}),
        ("search", "account.search", [
            (("query",), {"help": "Search query (partial name, case-insensitive)"}),
        ], {"epilog": _load_help("account_search")}),
    ]),
    ("article", "Article management", [
        ("create", "article.create", [
            (("--title",), {"required": True, "help": "Article title"}),
            (("--format",), {"default": "markdown", "choices": ["markdown", "typst"],
                             "help": "Source format"}),
            (("--content",), {"help": "Article body (inline; omit to open editor)"}),
            (("--no-editor",), {"action": "store_true", "help": "Create empty article without opening editor"}),
            (("--publish",), {"action": "store_true", "help": "Publish immediately after creation"}),
            (("--scores",), {"help": f'Self-review scores ({_SCORE_DIMS_LIST}), e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
        ], {"epilog": _load_help("article_create")}),
        ("show", "article.show", [
            (("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--show",), {"choices": ["meta", "full"], "default": "meta",
                           "help": "Display: meta (default), full (+content)"}),
        ], {"epilog": _load_help("article_show")}),
        ("list", "article.list", [
            (("--search",), {"help": "Fuzzy title search (case-insensitive)"}),
            (("--status",), {"choices": ["draft", "sedimentation", "published"],
                             "help": "Filter by status"}),
            (("--feed",), {"action": "store_true", "help": "Articles from followed users"}),
            (("--mine",), {"action": "store_true", "help": "My articles"}),
            (("--bookmarked",), {"action": "store_true", "help": "My bookmarked articles"}),
            (("--user",), {"help": "Show articles by this user (requires --server for remote fetch)"}),
            (("--server",), {"help": "Peer server URL for remote --user query"}),
        ], {"epilog": _load_help("article_list")}),
        ("edit", "article.edit", [
            (("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--content",), {"help": "New article body (omit to open editor)"}),
            (("--title",), {"help": "New article title"}),
            (("--no-editor",), {"action": "store_true", "help": "Skip editor; only apply --title if given"}),
        ], {"epilog": _load_help("article_edit")}),
        ("publish", "article.publish", [
            (("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--scores",), {"required": True,
                             "help": f'Self-review scores ({_SCORE_DIMS_LIST}), e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
        ], {"epilog": _load_help("article_publish")}),
        ("delete", "article.delete", [
            (("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--force",), {"action": "store_true", "help": "Delete without confirmation"}),
        ], {"epilog": _load_help("article_delete")}),
        ("scan", "article.scan", [], {"epilog": _load_help("article_scan")}),
        ("diff", "article.diff", [
            (("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("hash1",), {"help": "Old commit (hash, HEAD, or ~N)"}),
            (("hash2",), {"help": "New commit (hash, HEAD, or ~N)"}),
        ], {"epilog": _load_help("article_diff")}),
    ]),
    ("review", "Submit, invite, rate, and list peer reviews", [
        ("submit", "review.submit", [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--scores",), {"required": True,
                             "help": f'Five-dim scores ({_SCORE_DIMS_LIST}), e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
            (("--comment",), {"required": True, "help": "Review comment (min 200 characters)"}),
        ], {"epilog": _load_help("review_submit")}),
        ("list", "review.list", [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--show",), {"choices": ["meta", "full"], "default": "meta",
                           "help": "Display: meta (scores, default) or full (scores + threads)"}),
        ], {"epilog": _load_help("review_list")}),
        ("reply", "review.reply", [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--to",), {"required": True, "help": "Reviewer (@name, UUID, or prefix) to reply to"}),
        ], {"epilog": _load_help("review_reply")}),
        ("invite", "review.invite", [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--user",), {"required": True, "help": "User to invite (@name, UUID, or prefix)"}),
        ], {"epilog": _load_help("review_invite")}),
        ("accept", "review.accept", [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ], {"epilog": _load_help("review_accept")}),
        ("decline", "review.decline", [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ], {"epilog": _load_help("review_decline")}),
        ("rate", "review.rate", [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            (("--reviewer",), {"required": True, "help": "Reviewer to rate (@name, UUID, or prefix)"}),
            (("--helpfulness",), {"required": True, "type": int, "choices": [1, 2, 3, 4, 5],
             "help": "Helpfulness score 1-5"}),
        ], {"epilog": _load_help("review_rate")}),
    ]),
    ("merge", "Propose, accept, or withdraw merge proposals", [
        ("propose", "merge.propose", [
            (("fork_id",), {"help": "Your fork's article ID"}),
            (("--target",), {"required": True, "help": "Original article ID to merge into"}),
        ], {"epilog": _load_help("merge_propose")}),
        ("accept", "merge.accept", [
            (("proposal_id",), {"help": "Merge proposal ID"}),
            (("--target",), {"required": True, "help": "Target article ID"}),
        ], {"epilog": _load_help("merge_accept")}),
        ("withdraw", "merge.withdraw", [
            (("proposal_id",), {"help": "Merge proposal ID to withdraw"}),
        ], {"epilog": _load_help("merge_withdraw")}),
    ]),
    ("alias", "Set or manage aliases for followed users", [
        ("set", "alias.set", [
            (("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
            (("alias",), {"help": "Alias to assign"}),
        ], {"epilog": _load_help("alias_set")}),
        ("remove", "alias.remove", [
            (("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
        ], {"epilog": _load_help("alias_remove")}),
        ("list", "alias.list", [], {"epilog": _load_help("alias_list")}),
    ]),
    ("share", "Share or recommend articles to followers", [
        ("add", "share.add", [
            (("article_id",), {"help": "Article ID to share"}),
            (("--to",), {"help": "Target user (@name, @alias, or UUID)"}),
            (("--comment",), {"help": "Optional comment on the share"}),
        ], {"epilog": _load_help("share_add")}),
        ("list", "share.list", [
            (("--mine",), {"action": "store_true", "help": "Show my shares instead of feed"}),
        ], {"epilog": _load_help("share_list")}),
        ("remove", "share.remove", [
            (("article_id",), {"help": "Article ID to unshare"}),
        ], {"epilog": _load_help("share_remove")}),
    ]),
    ("bookmark", "Bookmark articles for later reading", [
        ("add", "bookmark.add", [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ], {"epilog": _load_help("bookmark_add")}),
        ("remove", "bookmark.remove", [
            (("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ], {"epilog": _load_help("bookmark_remove")}),
    ]),
    ("following", "View who a user follows", [
        ("", "following", [
            (("--user",), {"required": True, "help": "User ID to query"}),
            (("--local",), {"action": "store_true", "help": "Read from local DB"}),
            (("--server",), {"help": "Peer server URL"}),
        ]),
    ]),
    ("followers", "View who follows a user", [
        ("", "followers", [
            (("--user",), {"required": True, "help": "User ID to query"}),
            (("--local",), {"action": "store_true", "help": "Read from local DB"}),
            (("--server",), {"help": "Peer server URL"}),
        ]),
    ]),
    ("server", "Run the PeerPedia server", [
        ("start", "server.start", [
            (("--host",), {"default": "127.0.0.1", "help": "Bind address"}),
            (("--port",), {"default": 8080, "type": int, "help": "Listen port"}),
            (("--public-url",), {"default": "", "help": "Public URL for peer registration (e.g. https://peer.example.com)"}),
        ], {"epilog": _load_help("server_start")}),
    ]),
    ("sync", "Push/pull articles to/from a peer server", [
        ("status", "sync.status", [
            (("--server",), {"help": "Peer server URL (or set PEERPEDIA_SERVER env var)"}),
        ], {"epilog": _load_help("sync_status")}),
        ("pull", "sync.pull", [
            (("--server",), {"help": "Peer server URL (or set PEERPEDIA_SERVER env var)"}),
        ], {"epilog": _load_help("sync_pull")}),
        ("discover", "sync.discover", [
            (("--depth",), {"type": int, "default": 1, "help": "Follow graph depth (default 1)"}),
            (("--max-users",), {"type": int, "default": 100, "help": "Max users to traverse"}),
        ], {"epilog": _load_help("sync_discover")}),
    ]),
    ("notifications", "View and manage notifications", [
        ("", "notifications", [
            (("--all",), {"action": "store_true", "help": "Show all notifications (not just unread)"}),
        ], {"epilog": _load_help("notifications")}),
        ("read", "notifications.read", [
            (("notification_id",), {"help": "Notification ID to mark as read"}),
        ], {"epilog": _load_help("notifications_read")}),
    ]),
    ("maintainer", "Manage article co-authors (maintainers)", [
        ("add", "maintainer.add", [
            (("article_id",), {"help": "Article ID"}),
            (("--target-user",), {"required": True, "help": "User ID to add as maintainer"}),
        ], {"epilog": _load_help("maintainer_add")}),
        ("remove", "maintainer.remove", [
            (("article_id",), {"help": "Article ID"}),
            (("--target-user",), {"required": True, "help": "User ID to remove from maintainers"}),
        ], {"epilog": _load_help("maintainer_remove")}),
        ("list", "maintainer.list", [
            (("article_id",), {"help": "Article ID"}),
        ], {"epilog": _load_help("maintainer_list")}),
        ("consent", "maintainer.consent", [
            (("article_id",), {"help": "Article ID to consent to publish/merge"}),
        ], {"epilog": _load_help("maintainer_consent")}),
        ("revoke", "maintainer.revoke", [
            (("article_id",), {"help": "Article ID to revoke consent"}),
        ], {"epilog": _load_help("maintainer_revoke")}),
    ]),
]

# Top-level commands (no subparsers — just a single handler)
TOP_LEVEL = [
    ("schema", "schema", [
        (("command",), {"nargs": "?", "help": "Specific command name to describe"}),
    ]),
    ("fork", "fork", [
        (("article_id",), {"help": "Published article ID to fork"}),
    ], {"epilog": _load_help("fork")}),
    ("compile", "compile", [
        (("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        (("--format",), {"choices": ["pdf", "svg", "png", "html"],
                         "help": "Output format (default: pdf)"}),
    ], {"epilog": _load_help("compile")}),
    ("follow", "follow", [
        (("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
    ], {"epilog": _load_help("follow")}),
    ("unfollow", "unfollow", [
        (("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
    ], {"epilog": _load_help("unfollow")}),
    ("mother", "mother", []),
    ("school", "school", [
        (("--limit",), {"type": int, "default": 20, "help": "Max users to show"}),
        (("--server",), {"help": "Peer server URL (or set PEERPEDIA_SERVER env var)"}),
        (("--local",), {"action": "store_true", "help": "Read from local DB instead of peer server"}),
    ], {"epilog": _load_help("school")}),
    ("help", "help", [
        (("topic",), {"nargs": "?", "help": "Command or topic to get help about (default: meta help)"}),
    ]),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════

# Styled command overview in --help output.
_CMD_GROUPS = [
    ("Writing & publishing",                     ["article"]),
    ("Peer review",                              ["review"]),
    ("Collaboration (fork, merge, co-authors)",  ["merge", "fork", "maintainer"]),
    ("Social & discovery",                       ["follow", "unfollow", "following",
                                                  "followers", "school", "bookmark",
                                                  "share", "alias"]),
    ("Sync & networking",                        ["sync", "server"]),
    ("Account & utilities",                      ["account", "notifications",
                                                  "compile", "schema", "help", "mother"]),
]

_EXAMPLES = """\
EXAMPLES — real tasks you can copy and paste

  Your first paper:
    peerpedia account register --name "Albert Einstein"
    peerpedia article create --title "On the Electrodynamics of Moving Bodies"
    peerpedia article publish abc12345 --scores "orig=5,rigor=4,comp=4,ped=3,imp=5"

  Finding papers to read:
    peerpedia article list                          # all public papers
    peerpedia article list --search "quantum"       # papers about quantum topics
    peerpedia article list --feed                    # papers from people you follow
    peerpedia article show abc12345                  # read a paper's details
    peerpedia article show abc12345 --show full      # read the full text

  Improving your draft:
    peerpedia article edit abc12345                  # open editor to revise
    peerpedia article diff abc12345 ~1 HEAD          # see what changed last time

  Peer reviewing:
    peerpedia review submit abc12345 \\
        --scores "orig=4,rigor=3,comp=4,ped=3,imp=5" \\
        --comment "This paper presents a novel approach to..."
    peerpedia review list abc12345                   # see all reviews of a paper

  Working with others:
    peerpedia account search Einstein                # find a colleague
    peerpedia follow @einstein                       # follow their work
    peerpedia maintainer add abc12345 --target-user @bob  # add a co-author
    peerpedia fork abc12345                          # create your own copy to revise

  Sharing with peers:
    peerpedia sync push --server https://peer.example.com
    peerpedia sync pull --server https://peer.example.com

Add --help to any command for detailed options and more examples:
    peerpedia article create --help
    peerpedia review submit --help

New to the command line?  Run:  peerpedia mother"""


def _build_epilog() -> str:
    """Build the grouped command list for --help output."""
    _lookup: dict[str, tuple[str, str, list[str]]] = {}
    for name, help_text, subcommands in COMMAND_GROUPS:
        subs = [s[0] for s in subcommands if s[0]]
        _lookup[name] = (name, help_text, subs)
    for entry in TOP_LEVEL:
        _lookup[entry[0]] = (entry[0], entry[0], [])

    lines: list[str] = []
    for section, cmds in _CMD_GROUPS:
        lines.append(f"  {section}")
        for c in cmds:
            if c in _lookup:
                name, _help, subs = _lookup[c]
                if subs:
                    lines.append(f"    {name:<14} {', '.join(subs)}")
                else:
                    lines.append(f"    {name:<14} {_help}")
        lines.append("")
    return "\nCOMMANDS\n" + "\n".join(lines) + "\n" + _EXAMPLES


def _register_subparser(p, cmd_id: str) -> None:
    """Set command_id + dispatch on a subparser."""
    p.set_defaults(command_id=cmd_id, func=dispatch)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all subcommands registered."""
    import importlib.metadata

    try:
        _version = importlib.metadata.version("peerpedia-core")
    except importlib.metadata.PackageNotFoundError:
        _version = "unknown"

    parser = argparse.ArgumentParser(
        "peerpedia",
        description="PeerPedia — peer review from the terminal",
        epilog=_build_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version}")
    subs = parser.add_subparsers(dest="command")

    for name, help_text, subcommands in COMMAND_GROUPS:
        grp = subs.add_parser(name, help=help_text)
        grp_subs = grp.add_subparsers(dest="subcommand")
        for entry in subcommands:
            sub_name, cmd_id, arg_specs = entry[0], entry[1], entry[2]
            extra = entry[3] if len(entry) > 3 else {}
            epilog = extra.get("epilog", "")
            if sub_name == "":
                _add_args(grp, *arg_specs)
                _add_common(grp)
                _register_subparser(grp, cmd_id)
            else:
                p = grp_subs.add_parser(
                    sub_name, help=sub_name,
                    epilog=epilog,
                    formatter_class=argparse.RawDescriptionHelpFormatter,
                )
                _add_args(p, *arg_specs)
                _add_common(p)
                _register_subparser(p, cmd_id)

    for name, cmd_id, arg_specs, *_rest in TOP_LEVEL:
        extra = _rest[0] if _rest else {}
        p = subs.add_parser(
            name, help=name,
            epilog=extra.get("epilog", ""),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        _add_args(p, *arg_specs)
        _add_common(p)
        _register_subparser(p, cmd_id)

    return parser


def get_cmd_map() -> dict[str, list[str]]:
    """Return ``{flat_cmd: [group, subcmd]}`` for the REPL dispatcher.

    Delegates to ``dispatch.get_cmd_map_for_parser()`` for a single source
    of truth derived from ``_HANDLER_MAP``.
    """
    from peerpedia_core.cli.dispatch import get_cmd_map_for_parser
    return get_cmd_map_for_parser()
