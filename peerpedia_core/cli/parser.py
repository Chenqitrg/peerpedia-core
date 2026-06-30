# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Argument parser — declarative command definitions, single builder loop."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from peerpedia_core.cli.dispatch import dispatch
from peerpedia_core.types.scores import SCORE_FORMAT_EXAMPLE, _SCORE_DIMS_LIST

_HELP_DIR = Path(__file__).resolve().parent / "help"


def _load_help(name: str) -> str:
    path = _HELP_DIR / f"{name}.txt"
    return path.read_text() if path.is_file() else ""


# ═══════════════════════════════════════════════════════════════════════════════
# Command definition types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ArgSpec:
    args: tuple[str, ...]
    kwargs: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Command:
    name: str           # CLI subcommand name ("" = commands live directly on the group parser)
    cmd_id: str         # dispatch command_id
    args: list[ArgSpec] = field(default_factory=list)
    help_file: str = ""  # extended help file name, loaded on access

    @property
    def help_epilog(self) -> str:
        """Extended help text loaded from ``cli/help/<help_file>.txt``."""
        return _load_help(self.help_file) if self.help_file else ""


@dataclass(frozen=True)
class CommandGroup:
    name: str
    help: str
    commands: list[Command]


# ═══════════════════════════════════════════════════════════════════════════════
# Command definitions
# ═══════════════════════════════════════════════════════════════════════════════

COMMANDS: list[CommandGroup | Command] = [
    # ── Groups ────────────────────────────────────────────────────────────
    CommandGroup("account", "Account management", [
        Command("register", "account.register", [
            ArgSpec(("--name",), {"required": True, "help": "Your display name"}),
            ArgSpec(("--password",), {"help": "Password (omit for interactive prompt; or set PEERPEDIA_PASSWORD env var)"}),
        ], help_file="account_register"),
        Command("login", "account.login", [
            ArgSpec(("--name",), {"required": True, "help": "Your display name"}),
            ArgSpec(("--password",), {"help": "Password (omit for interactive prompt; or set PEERPEDIA_PASSWORD env var)"}),
            ArgSpec(("--peer",), {"help": "Peer server URL for remote bootstrap on a new device"}),
            ArgSpec(("--user-id",), {"help": "User UUID for remote bootstrap (needed on new devices)"}),
        ], help_file="account_login"),
        Command("recover", "account.recover", [
            ArgSpec(("--name",), {"help": "Your display name"}),
            ArgSpec(("--user-id",), {"help": "Your user ID (UUID)"}),
        ], help_file="account_recover"),
        Command("whoami", "account.whoami", [
            ArgSpec(("--verbose",), {"action": "store_true", "help": "Show user ID, public key, and salt for device bootstrap"}),
        ], help_file="account_whoami"),
        Command("bootstrap", "account.bootstrap", [
            ArgSpec(("--from",), {"required": True, "dest": "from_", "metavar": "JSON",
                     "help": "JSON blob from 'account whoami --verbose --json'"}),
            ArgSpec(("--peer",), {"help": "Peer URL for data sync after bootstrap"}),
        ], help_file="account_bootstrap"),
        Command("delete", "account.delete", [], help_file="account_delete"),
        Command("search", "account.search", [
            ArgSpec(("query",), {"help": "Search query (partial name, case-insensitive)"}),
        ], help_file="account_search"),
    ]),
    CommandGroup("article", "Article management", [
        Command("create", "article.create", [
            ArgSpec(("--title",), {"required": True, "help": "Article title"}),
            ArgSpec(("--format",), {"default": "markdown", "choices": ["markdown", "typst"], "help": "Source format"}),
            ArgSpec(("--content",), {"help": "Article body (inline; omit to open editor)"}),
            ArgSpec(("--no-editor",), {"action": "store_true", "help": "Create empty article without opening editor"}),
            ArgSpec(("--publish",), {"action": "store_true", "help": "Publish immediately after creation"}),
            ArgSpec(("--scores",), {"help": f'Self-review scores ({_SCORE_DIMS_LIST}), e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
        ], help_file="article_create"),
        Command("show", "article.show", [
            ArgSpec(("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            ArgSpec(("--show",), {"choices": ["meta", "full"], "default": "meta",
                                  "help": "Display: meta (default), full (+content)"}),
        ], help_file="article_show"),
        Command("list", "article.list", [
            ArgSpec(("--search",), {"help": "Fuzzy title search (case-insensitive)"}),
            ArgSpec(("--status",), {"choices": ["draft", "sedimentation", "published"], "help": "Filter by status"}),
            ArgSpec(("--feed",), {"action": "store_true", "help": "Articles from followed users"}),
            ArgSpec(("--mine",), {"action": "store_true", "help": "My articles"}),
            ArgSpec(("--bookmarked",), {"action": "store_true", "help": "My bookmarked articles"}),
            ArgSpec(("--user",), {"help": "Show articles by this user (requires --server for remote fetch)"}),
            ArgSpec(("--server",), {"help": "Peer server URL for remote --user query"}),
        ], help_file="article_list"),
        Command("edit", "article.edit", [
            ArgSpec(("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            ArgSpec(("--content",), {"help": "New article body (omit to open editor)"}),
            ArgSpec(("--title",), {"help": "New article title"}),
            ArgSpec(("--no-editor",), {"action": "store_true", "help": "Skip editor; only apply --title if given"}),
        ], help_file="article_edit"),
        Command("publish", "article.publish", [
            ArgSpec(("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            ArgSpec(("--scores",), {"required": True,
                     "help": f'Self-review scores ({_SCORE_DIMS_LIST}), e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
        ], help_file="article_publish"),
        Command("delete", "article.delete", [
            ArgSpec(("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            ArgSpec(("--force",), {"action": "store_true", "help": "Delete without confirmation"}),
        ], help_file="article_delete"),
        Command("scan", "article.scan", [], help_file="article_scan"),
        Command("diff", "article.diff", [
            ArgSpec(("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            ArgSpec(("hash1",), {"help": "Old commit (hash, HEAD, or ~N)"}),
            ArgSpec(("hash2",), {"help": "New commit (hash, HEAD, or ~N)"}),
        ], help_file="article_diff"),
    ]),
    CommandGroup("review", "Submit, invite, rate, and list peer reviews", [
        Command("submit", "review.submit", [
            ArgSpec(("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            ArgSpec(("--scores",), {"required": True,
                     "help": f'Five-dim scores ({_SCORE_DIMS_LIST}), e.g. "{SCORE_FORMAT_EXAMPLE}"'}),
            ArgSpec(("--comment",), {"required": True, "help": "Review comment (min 200 characters)"}),
        ], help_file="review_submit"),
        Command("list", "review.list", [
            ArgSpec(("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            ArgSpec(("--show",), {"choices": ["meta", "full"], "default": "meta",
                                  "help": "Display: meta (scores, default) or full (scores + threads)"}),
        ], help_file="review_list"),
        Command("reply", "review.reply", [
            ArgSpec(("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            ArgSpec(("--to",), {"required": True, "help": "Reviewer (@name, UUID, or prefix) to reply to"}),
        ], help_file="review_reply"),
        Command("invite", "review.invite", [
            ArgSpec(("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            ArgSpec(("--user",), {"required": True, "help": "User to invite (@name, UUID, or prefix)"}),
        ], help_file="review_invite"),
        Command("accept", "review.accept", [
            ArgSpec(("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ], help_file="review_accept"),
        Command("decline", "review.decline", [
            ArgSpec(("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ], help_file="review_decline"),
        Command("rate", "review.rate", [
            ArgSpec(("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
            ArgSpec(("--reviewer",), {"required": True, "help": "Reviewer to rate (@name, UUID, or prefix)"}),
            ArgSpec(("--helpfulness",), {"required": True, "type": int, "choices": [1, 2, 3, 4, 5],
                     "help": "Helpfulness score 1-5"}),
        ], help_file="review_rate"),
    ]),
    CommandGroup("merge", "Propose, accept, or withdraw merge proposals", [
        Command("propose", "merge.propose", [
            ArgSpec(("fork_id",), {"help": "Your fork's article ID"}),
            ArgSpec(("--target",), {"required": True, "help": "Original article ID to merge into"}),
        ], help_file="merge_propose"),
        Command("accept", "merge.accept", [
            ArgSpec(("proposal_id",), {"help": "Merge proposal ID"}),
            ArgSpec(("--target",), {"required": True, "help": "Target article ID"}),
        ], help_file="merge_accept"),
        Command("withdraw", "merge.withdraw", [
            ArgSpec(("proposal_id",), {"help": "Merge proposal ID to withdraw"}),
        ], help_file="merge_withdraw"),
    ]),
    CommandGroup("alias", "Set or manage aliases for followed users", [
        Command("set", "alias.set", [
            ArgSpec(("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
            ArgSpec(("alias",), {"help": "Alias to assign"}),
        ], help_file="alias_set"),
        Command("remove", "alias.remove", [
            ArgSpec(("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
        ], help_file="alias_remove"),
        Command("list", "alias.list", [], help_file="alias_list"),
    ]),
    CommandGroup("share", "Share or recommend articles to followers", [
        Command("add", "share.add", [
            ArgSpec(("article_id",), {"help": "Article ID to share"}),
            ArgSpec(("--to",), {"help": "Target user (@name, @alias, or UUID)"}),
            ArgSpec(("--comment",), {"help": "Optional comment on the share"}),
        ], help_file="share_add"),
        Command("list", "share.list", [
            ArgSpec(("--mine",), {"action": "store_true", "help": "Show my shares instead of feed"}),
        ], help_file="share_list"),
        Command("remove", "share.remove", [
            ArgSpec(("article_id",), {"help": "Article ID to unshare"}),
        ], help_file="share_remove"),
    ]),
    CommandGroup("bookmark", "Bookmark articles for later reading", [
        Command("add", "bookmark.add", [
            ArgSpec(("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ], help_file="bookmark_add"),
        Command("remove", "bookmark.remove", [
            ArgSpec(("article_id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ], help_file="bookmark_remove"),
    ]),
    CommandGroup("following", "View who a user follows", [
        Command("", "following", [
            ArgSpec(("--user",), {"required": True, "help": "User ID to query"}),
            ArgSpec(("--local",), {"action": "store_true", "help": "Read from local DB"}),
            ArgSpec(("--server",), {"help": "Peer server URL"}),
        ]),
    ]),
    CommandGroup("followers", "View who follows a user", [
        Command("", "followers", [
            ArgSpec(("--user",), {"required": True, "help": "User ID to query"}),
            ArgSpec(("--local",), {"action": "store_true", "help": "Read from local DB"}),
            ArgSpec(("--server",), {"help": "Peer server URL"}),
        ]),
    ]),
    CommandGroup("server", "Run the PeerPedia server", [
        Command("start", "server.start", [
            ArgSpec(("--host",), {"default": "127.0.0.1", "help": "Bind address"}),
            ArgSpec(("--port",), {"default": 8080, "type": int, "help": "Listen port"}),
            ArgSpec(("--public-url",), {"default": "", "help": "Public URL for peer registration (e.g. https://peer.example.com)"}),
        ], help_file="server_start"),
    ]),
    CommandGroup("sync", "Push/pull articles to/from a peer server", [
        Command("status", "sync.status", [
            ArgSpec(("--server",), {"help": "Peer server URL (or set PEERPEDIA_SERVER env var)"}),
        ], help_file="sync_status"),
        Command("pull", "sync.pull", [
            ArgSpec(("--server",), {"help": "Peer server URL (or set PEERPEDIA_SERVER env var)"}),
        ], help_file="sync_pull"),
        Command("discover", "sync.discover", [
            ArgSpec(("--depth",), {"type": int, "default": 1, "help": "Follow graph depth (default 1)"}),
            ArgSpec(("--max-users",), {"type": int, "default": 100, "help": "Max users to traverse"}),
        ], help_file="sync_discover"),
    ]),
    CommandGroup("notifications", "View and manage notifications", [
        Command("", "notifications", [
            ArgSpec(("--all",), {"action": "store_true", "help": "Show all notifications (not just unread)"}),
        ], help_file="notifications"),
        Command("read", "notifications.read", [
            ArgSpec(("notification_id",), {"help": "Notification ID to mark as read"}),
        ], help_file="notifications_read"),
    ]),
    CommandGroup("maintainer", "Manage article co-authors (maintainers)", [
        Command("add", "maintainer.add", [
            ArgSpec(("article_id",), {"help": "Article ID"}),
            ArgSpec(("--target-user",), {"required": True, "help": "User ID to add as maintainer"}),
        ], help_file="maintainer_add"),
        Command("remove", "maintainer.remove", [
            ArgSpec(("article_id",), {"help": "Article ID"}),
            ArgSpec(("--target-user",), {"required": True, "help": "User ID to remove from maintainers"}),
        ], help_file="maintainer_remove"),
        Command("list", "maintainer.list", [
            ArgSpec(("article_id",), {"help": "Article ID"}),
        ], help_file="maintainer_list"),
        Command("consent", "maintainer.consent", [
            ArgSpec(("article_id",), {"help": "Article ID to consent to publish/merge"}),
        ], help_file="maintainer_consent"),
        Command("revoke", "maintainer.revoke", [
            ArgSpec(("article_id",), {"help": "Article ID to revoke consent"}),
        ], help_file="maintainer_revoke"),
    ]),

    # ── Top-level commands ────────────────────────────────────────────────
    Command("schema", "schema", [
        ArgSpec(("command",), {"nargs": "?", "help": "Specific command name to describe"}),
    ]),
    Command("fork", "fork", [
        ArgSpec(("article_id",), {"help": "Published article ID to fork"}),
    ], help_file="fork"),
    Command("compile", "compile", [
        ArgSpec(("id",), {"metavar": "ref", "help": "Article UUID, prefix, or title keyword"}),
        ArgSpec(("--format",), {"choices": ["pdf", "svg", "png", "html"], "help": "Output format (default: pdf)"}),
    ], help_file="compile"),
    Command("follow", "follow", [
        ArgSpec(("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
    ], help_file="follow"),
    Command("unfollow", "unfollow", [
        ArgSpec(("user_identifier",), {"help": "User ID, @name, or UUID prefix"}),
    ], help_file="unfollow"),
    Command("mother", "mother", [], help_file="mother"),
    Command("school", "school", [
        ArgSpec(("--limit",), {"type": int, "default": 20, "help": "Max users to show"}),
        ArgSpec(("--server",), {"help": "Peer server URL (or set PEERPEDIA_SERVER env var)"}),
        ArgSpec(("--local",), {"action": "store_true", "help": "Read from local DB instead of peer server"}),
    ], help_file="school"),
    Command("help", "help", [
        ArgSpec(("topic",), {"nargs": "?", "help": "Command or topic to get help about (default: meta help)"}),
    ]),
]


# ═══════════════════════════════════════════════════════════════════════════════
# Help epilog
# ═══════════════════════════════════════════════════════════════════════════════

_SECTIONS = [
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

_NAME_WIDTH = 14  # help output column alignment


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
    # ── Index: name → Command | CommandGroup ──────────────────────────
    index: dict[str, Command | CommandGroup] = {}
    for item in COMMANDS:
        index[item.name] = item
        if isinstance(item, CommandGroup):
            for cmd in item.commands:
                if cmd.name:
                    index[cmd.name] = cmd

    # ── Render ────────────────────────────────────────────────────────
    lines: list[str] = []
    for section, names in _SECTIONS:
        lines.append(f"  {section}")
        for n in names:
            item = index.get(n)
            if item is None:
                continue
            if isinstance(item, CommandGroup):
                subs = [c.name for c in item.commands if c.name]
                lines.append(f"    {item.name:<{_NAME_WIDTH}} {', '.join(subs)}")
            else:
                lines.append(f"    {item.name:<{_NAME_WIDTH}} {item.name}")
        lines.append("")
    return "\nCOMMANDS\n" + "\n".join(lines) + "\n" + _EXAMPLES


# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════

_COMMON_ARGS = [
    (("--json",), {"action": "store_true", "help": "Output as JSON"}),
    (("--rich",), {"action": "store_true", "help": "Output as human-readable Rich text"}),
]


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser from the COMMANDS table."""
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

    for item in COMMANDS:
        if isinstance(item, CommandGroup):
            grp = subs.add_parser(item.name, help=item.help)
            sub = grp.add_subparsers(dest="subcommand")
            for cmd in item.commands:
                _register(_target_parser(grp, sub, cmd), cmd)
        else:
            _register(_target_parser(subs, subs, item), item)

    return parser


def _target_parser(group_parser, subparsers, cmd: Command) -> argparse.ArgumentParser:
    """Return the parser to register *cmd* on — group or subparser."""
    if cmd.name == "":
        return group_parser
    return subparsers.add_parser(
        cmd.name, help=cmd.name,
        epilog=cmd.help_epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def _register(p: argparse.ArgumentParser, cmd: Command) -> None:
    """Add args, common args, and dispatch to a parser."""
    for spec in cmd.args:
        p.add_argument(*spec.args, **spec.kwargs)
    for args, kwargs in _COMMON_ARGS:
        p.add_argument(*args, **kwargs)
    p.set_defaults(command_id=cmd.cmd_id, func=dispatch)


