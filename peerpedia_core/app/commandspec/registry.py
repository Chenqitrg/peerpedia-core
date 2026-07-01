# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Command registry — every command in one place.

``COMMAND_GROUPS`` and ``TOP_LEVEL_COMMANDS`` are the single source of truth
for all CLI/REPL commands.  The lookup index is built once at import time
and queried via ``find_spec()`` and ``spec_for_cmd_id()``.
"""

from __future__ import annotations

from peerpedia_core.app.commandspec import handlers as _h
from peerpedia_core.app.commandspec.types import (
    ArgSpec, CommandSpec, CommandGroupSpec,
)
from peerpedia_core.types.scores import SCORE_FORMAT_EXAMPLE, _SCORE_DIMS_LIST
from peerpedia_core.types.status import ArticleStatus

# ═══════════════════════════════════════════════════════════════════════════════
# Shared help strings
# ═══════════════════════════════════════════════════════════════════════════════

_SCORES_HELP = f'Self-review scores ({_SCORE_DIMS_LIST}), e.g. "{SCORE_FORMAT_EXAMPLE}"'


# ═══════════════════════════════════════════════════════════════════════════════
# Command groups
# ═══════════════════════════════════════════════════════════════════════════════

COMMAND_GROUPS: list[CommandGroupSpec] = [
    CommandGroupSpec("account", "Account management", [
        CommandSpec("account.register", "account", "register", handler=_h.register, effect="destructive", help_file="account_register", args=[
            ArgSpec("name", required=True, help="Your display name"),
            ArgSpec("password", help="Password (omit for interactive prompt; or set PEERPEDIA_PASSWORD env var)"),
        ]),
        CommandSpec("account.login", "account", "login", handler=_h.login, help_file="account_login", args=[
            ArgSpec("name", required=True, help="Your display name"),
            ArgSpec("password", help="Password (omit for interactive prompt; or set PEERPEDIA_PASSWORD env var)"),
            ArgSpec("peer", help="Peer server URL for remote bootstrap on a new device"),
            ArgSpec("user_id", help="User UUID for remote bootstrap (needed on new devices)"),
        ]),
        CommandSpec("account.recover", "account", "recover", handler=_h.recover, effect="destructive", help_file="account_recover", args=[
            ArgSpec("name", help="Your display name"),
            ArgSpec("user_id", help="Your user ID (UUID)"),
            ArgSpec("password", help="Password (omit for interactive prompt)"),
        ]),
        CommandSpec("account.whoami", "account", "whoami", handler=_h.whoami, help_file="account_whoami", args=[
            ArgSpec("verbose", takes_value=False, help="Show user ID, public key, and salt for device bootstrap"),
        ]),
        CommandSpec("account.bootstrap", "account", "bootstrap", handler=_h.bootstrap, effect="destructive", help_file="account_bootstrap", args=[
            ArgSpec("from_", required=True, metavar="JSON",
                    help="JSON blob from 'account whoami --verbose --json'"),
            ArgSpec("peer", help="Peer URL for data sync after bootstrap"),
        ]),
        CommandSpec("account.delete", "account", "delete", handler=_h.account_delete, effect="destructive", help_file="account_delete", args=[]),
        CommandSpec("account.search", "account", "search", handler=_h.account_search, help_file="account_search", args=[
            ArgSpec("query", positional=True, help="Search query (partial name, case-insensitive)"),
        ]),
    ]),
    CommandGroupSpec("article", "Article management", [
        CommandSpec("article.create", "article", "create", handler=_h.article_create, effect="write", help_file="article_create", args=[
            ArgSpec("title", required=True, help="Article title"),
            ArgSpec("format", default="markdown", choices=["markdown", "typst"], help="Source format"),
            ArgSpec("content", help="Article body (inline; omit to open editor)"),
            ArgSpec("no_editor", takes_value=False, help="Create empty article without opening editor"),
            ArgSpec("publish", takes_value=False, help="Publish immediately after creation"),
            ArgSpec("scores", help=_SCORES_HELP),
        ]),
        CommandSpec("article.show", "article", "show", handler=_h.article_show, help_file="article_show", args=[
            ArgSpec("id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
            ArgSpec("show", default="meta", choices=["meta", "full"], help="Display: meta (default), full (+content)"),
        ]),
        CommandSpec("article.list", "article", "list", handler=_h.article_list, help_file="article_list", args=[
            ArgSpec("search", help="Fuzzy title search (case-insensitive)"),
            ArgSpec("status", choices=[ArticleStatus.DRAFT, ArticleStatus.SEDIMENTATION, ArticleStatus.PUBLISHED], help="Filter by status"),
            ArgSpec("feed", takes_value=False, help="Articles from followed users"),
            ArgSpec("mine", choices=["maintainer", "author"], help="My articles as maintainer (default) or author"),
            ArgSpec("bookmarked", takes_value=False, help="My bookmarked articles"),
            ArgSpec("user", help="Show articles by this user (requires --server for remote fetch)"),
            ArgSpec("server", help="Peer server URL for remote --user query"),
            ArgSpec("limit", type=int, default=20, help="Max articles to show"),
        ]),
        CommandSpec("article.edit", "article", "edit", handler=_h.article_edit, effect="write", help_file="article_edit", args=[
            ArgSpec("id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
            ArgSpec("content", help="New article body (omit to open editor)"),
            ArgSpec("title", help="New article title"),
            ArgSpec("no_editor", takes_value=False, help="Skip editor; only apply --title if given"),
            ArgSpec("message", help="Commit message (REPL only; CLI prompts interactively)"),
        ]),
        CommandSpec("article.publish", "article", "publish", handler=_h.article_publish, effect="write", help_file="article_publish", args=[
            ArgSpec("id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
            ArgSpec("scores", required=True, help=_SCORES_HELP),
        ]),
        CommandSpec("article.delete", "article", "delete", handler=_h.article_delete, effect="destructive", help_file="article_delete", args=[
            ArgSpec("id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
            ArgSpec("force", takes_value=False, help="Delete without confirmation"),
        ]),
        CommandSpec("article.scan", "article", "scan", handler=_h.article_scan, effect="write", help_file="article_scan", args=[]),
        CommandSpec("article.diff", "article", "diff", handler=_h.article_diff, help_file="article_diff", args=[
            ArgSpec("id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
            ArgSpec("hash1", positional=True, help="Old commit (hash, HEAD, or ~N)"),
            ArgSpec("hash2", positional=True, help="New commit (hash, HEAD, or ~N)"),
        ]),
    ]),
    CommandGroupSpec("review", "Submit, invite, rate, and list peer reviews", [
        CommandSpec("review.submit", "review", "submit", handler=_h.review_submit, effect="write", help_file="review_submit", args=[
            ArgSpec("article_id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
            ArgSpec("scores", required=True, help=_SCORES_HELP),
            ArgSpec("comment", required=True, help="Review comment (min 200 characters)"),
        ]),
        CommandSpec("review.list", "review", "list", handler=_h.review_list, help_file="review_list", args=[
            ArgSpec("article_id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
            ArgSpec("show", default="meta", choices=["meta", "full"],
                    help="Display: meta (scores, default) or full (scores + threads)"),
        ]),
        CommandSpec("review.reply", "review", "reply", handler=_h.review_reply, effect="write", help_file="review_reply", args=[
            ArgSpec("article_id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
            ArgSpec("to", required=True, help="Reviewer (@name, UUID, or prefix) to reply to"),
            ArgSpec("content", help="Reply body (REPL only; CLI opens editor)"),
        ]),
        CommandSpec("review.invite", "review", "invite", handler=_h.review_invite, effect="write", help_file="review_invite", args=[
            ArgSpec("article_id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
            ArgSpec("user", required=True, help="User to invite (@name, UUID, or prefix)"),
        ]),
        CommandSpec("review.accept", "review", "accept", handler=_h.review_accept, effect="write", help_file="review_accept", args=[
            ArgSpec("article_id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
        ]),
        CommandSpec("review.decline", "review", "decline", handler=_h.review_decline, effect="write", help_file="review_decline", args=[
            ArgSpec("article_id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
        ]),
        CommandSpec("review.rate", "review", "rate", handler=_h.review_rate, effect="write", help_file="review_rate", args=[
            ArgSpec("article_id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
            ArgSpec("reviewer", required=True, help="Reviewer to rate (@name, UUID, or prefix)"),
            ArgSpec("helpfulness", required=True, type=int, choices=[1, 2, 3, 4, 5],
                    help="Helpfulness score 1-5"),
        ]),
    ]),
    CommandGroupSpec("merge", "Propose, accept, or withdraw merge proposals", [
        CommandSpec("merge.propose", "merge", "propose", handler=_h.merge_propose, effect="write", help_file="merge_propose", args=[
            ArgSpec("fork_id", positional=True, help="Your fork's article ID"),
            ArgSpec("target", required=True, help="Original article ID to merge into"),
        ]),
        CommandSpec("merge.accept", "merge", "accept", handler=_h.merge_accept, effect="destructive", help_file="merge_accept", args=[
            ArgSpec("proposal_id", positional=True, help="Merge proposal ID"),
            ArgSpec("target", required=True, help="Target article ID"),
        ]),
        CommandSpec("merge.withdraw", "merge", "withdraw", handler=_h.merge_withdraw, effect="write", help_file="merge_withdraw", args=[
            ArgSpec("proposal_id", positional=True, help="Merge proposal ID to withdraw"),
        ]),
    ]),
    CommandGroupSpec("alias", "Set or manage aliases for followed users", [
        CommandSpec("alias.set", "alias", "set", handler=_h.alias_set, effect="write", help_file="alias_set", args=[
            ArgSpec("user_identifier", positional=True, help="User ID, @name, or UUID prefix"),
            ArgSpec("alias", positional=True, help="Alias to assign"),
        ]),
        CommandSpec("alias.remove", "alias", "remove", handler=_h.alias_remove, effect="write", help_file="alias_remove", args=[
            ArgSpec("user_identifier", positional=True, help="User ID, @name, or UUID prefix"),
        ]),
        CommandSpec("alias.list", "alias", "list", handler=_h.alias_list, help_file="alias_list", args=[]),
    ]),
    CommandGroupSpec("share", "Share or recommend articles to followers", [
        CommandSpec("share.add", "share", "add", handler=_h.share_add, effect="write", help_file="share_add", args=[
            ArgSpec("article_id", positional=True, help="Article ID to share"),
            ArgSpec("to", help="Target user (@name, @alias, or UUID)"),
            ArgSpec("comment", help="Optional comment on the share"),
        ]),
        CommandSpec("share.list", "share", "list", handler=_h.share_list, help_file="share_list", args=[
            ArgSpec("mine", takes_value=False, help="Show my shares instead of feed"),
        ]),
        CommandSpec("share.remove", "share", "remove", handler=_h.share_remove, effect="write", help_file="share_remove", args=[
            ArgSpec("article_id", positional=True, help="Article ID to unshare"),
        ]),
    ]),
    CommandGroupSpec("bookmark", "Bookmark articles for later reading", [
        CommandSpec("bookmark.add", "bookmark", "add", handler=_h.bookmark_add, effect="write", help_file="bookmark_add", args=[
            ArgSpec("article_id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
        ]),
        CommandSpec("bookmark.remove", "bookmark", "remove", handler=_h.bookmark_remove, effect="write", help_file="bookmark_remove", args=[
            ArgSpec("article_id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
        ]),
    ]),
    CommandGroupSpec("following", "View who a user follows", [
        CommandSpec("following", "following", None, handler=_h.following, args=[
            ArgSpec("user", required=True, help="User ID to query"),
            ArgSpec("local", takes_value=False, help="Read from local DB"),
            ArgSpec("server", help="Peer server URL"),
        ]),
    ]),
    CommandGroupSpec("followers", "View who follows a user", [
        CommandSpec("followers", "followers", None, handler=_h.followers, args=[
            ArgSpec("user", required=True, help="User ID to query"),
            ArgSpec("local", takes_value=False, help="Read from local DB"),
            ArgSpec("server", help="Peer server URL"),
        ]),
    ]),
    CommandGroupSpec("server", "Run the PeerPedia server", [
        CommandSpec("server.start", "server", "start", help_file="server_start", frontend="cli", effect="external", args=[
            ArgSpec("host", default="127.0.0.1", help="Bind address"),
            ArgSpec("port", type=int, default=8080, help="Listen port"),
            ArgSpec("public_url", default="", help="Public URL for peer registration (e.g. https://peer.example.com)"),
        ]),
    ]),
    CommandGroupSpec("sync", "Push/pull articles to/from a peer server", [
        CommandSpec("sync.status", "sync", "status", handler=_h.sync_status, help_file="sync_status", args=[
            ArgSpec("server", help="Peer server URL (or set PEERPEDIA_SERVER env var)"),
        ]),
        CommandSpec("sync.pull", "sync", "pull", handler=_h.sync_pull, effect="external", help_file="sync_pull", args=[
            ArgSpec("server", help="Peer server URL (or set PEERPEDIA_SERVER env var)"),
        ]),
        CommandSpec("sync.discover", "sync", "discover", handler=_h.sync_discover, effect="external", help_file="sync_discover", args=[
            ArgSpec("server", help="Peer server URL (or set PEERPEDIA_SERVER env var)"),
            ArgSpec("depth", type=int, default=1, help="Follow graph depth (default 1)"),
            ArgSpec("max_users", type=int, default=100, help="Max users to traverse"),
        ]),
    ]),
    CommandGroupSpec("notifications", "View and manage notifications", [
        CommandSpec("notifications", "notifications", None, handler=_h.notifications, help_file="notifications", args=[
            ArgSpec("all", takes_value=False, help="Show all notifications (not just unread)"),
        ]),
        CommandSpec("notifications.read", "notifications", "read", handler=_h.notifications_read, effect="write", help_file="notifications_read", args=[
            ArgSpec("notification_id", positional=True, help="Notification ID to mark as read"),
        ]),
    ]),
    CommandGroupSpec("maintainer", "Manage article co-authors (maintainers)", [
        CommandSpec("maintainer.add", "maintainer", "add", handler=_h.maintainer_add, effect="write", help_file="maintainer_add", args=[
            ArgSpec("article_id", positional=True, help="Article ID"),
            ArgSpec("target_user", required=True, help="User ID to add as maintainer"),
        ]),
        CommandSpec("maintainer.remove", "maintainer", "remove", handler=_h.maintainer_remove, effect="write", help_file="maintainer_remove", args=[
            ArgSpec("article_id", positional=True, help="Article ID"),
            ArgSpec("target_user", required=True, help="User ID to remove from maintainers"),
        ]),
        CommandSpec("maintainer.list", "maintainer", "list", handler=_h.maintainer_list, help_file="maintainer_list", args=[
            ArgSpec("article_id", positional=True, help="Article ID"),
        ]),
        CommandSpec("maintainer.consent", "maintainer", "consent", handler=_h.maintainer_consent, effect="write", help_file="maintainer_consent", args=[
            ArgSpec("article_id", positional=True, help="Article ID to consent to publish/merge"),
        ]),
        CommandSpec("maintainer.revoke", "maintainer", "revoke", handler=_h.maintainer_revoke, effect="write", help_file="maintainer_revoke", args=[
            ArgSpec("article_id", positional=True, help="Article ID to revoke consent"),
        ]),
    ]),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Top-level commands (no group)
# ═══════════════════════════════════════════════════════════════════════════════

TOP_LEVEL_COMMANDS: list[CommandSpec] = [
    CommandSpec("fork", "", None, handler=_h.fork, effect="write", help_file="fork", args=[
        ArgSpec("article_id", positional=True, help="Published article ID to fork"),
    ]),
    CommandSpec("follow", "", None, handler=_h.follow, effect="write", help_file="follow", args=[
        ArgSpec("user_identifier", positional=True, help="User ID, @name, or UUID prefix"),
    ]),
    CommandSpec("unfollow", "", None, handler=_h.unfollow, effect="write", help_file="unfollow", args=[
        ArgSpec("user_identifier", positional=True, help="User ID, @name, or UUID prefix"),
    ]),
    CommandSpec("school", "", None, handler=_h.school, help_file="school", args=[
        ArgSpec("limit", type=int, default=20, help="Max users to show"),
        ArgSpec("server", help="Peer server URL (or set PEERPEDIA_SERVER env var)"),
        ArgSpec("local", takes_value=False, help="Read from local DB instead of peer server"),
    ]),
    # CLI-only top-level commands
    CommandSpec("schema", "", None, frontend="cli", args=[
        ArgSpec("command", positional=True, default="", help="Specific command name to describe"),
    ]),
    CommandSpec("compile", "", None, help_file="compile", frontend="cli", effect="external", args=[
        ArgSpec("id", positional=True, metavar="ref", help="Article UUID, prefix, or title keyword"),
        ArgSpec("format", choices=["pdf", "svg", "png", "html"], help="Output format (default: pdf)"),
    ]),
    CommandSpec("mother", "", None, help_file="mother", frontend="cli", args=[]),
    CommandSpec("help", "", None, frontend="cli", args=[
        ArgSpec("topic", positional=True, default="", help="Command or topic to get help about (default: meta help)"),
    ]),
]


# ═══════════════════════════════════════════════════════════════════════════════
# Lookup index  —  built once at import time
# ═══════════════════════════════════════════════════════════════════════════════

_COMMAND_BY_KEY: dict[tuple[str, str | None], CommandSpec] = {}
_COMMAND_BY_ID: dict[str, CommandSpec] = {}


def _build_index() -> None:
    for grp in COMMAND_GROUPS:
        for cmd in grp.commands:
            _COMMAND_BY_KEY[(cmd.group, cmd.action)] = cmd
            _COMMAND_BY_ID[cmd.cmd_id] = cmd
    for cmd in TOP_LEVEL_COMMANDS:
        _COMMAND_BY_KEY[(cmd.group or cmd.cmd_id, cmd.action)] = cmd
        _COMMAND_BY_ID[cmd.cmd_id] = cmd


_build_index()


def find_spec(group: str, action: str | None) -> CommandSpec | None:
    """Look up a command spec by (group, action) pair."""
    return _COMMAND_BY_KEY.get((group, action))


def spec_for_cmd_id(cmd_id: str) -> CommandSpec | None:
    """Look up a command spec by dotted ``cmd_id`` (e.g. ``"article.create"``)."""
    return _COMMAND_BY_ID.get(cmd_id)
