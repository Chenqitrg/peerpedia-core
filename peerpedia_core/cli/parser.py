# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Argument parser — maps CLI commands to handler functions.

Layer 3 of the CLI package.  Imports every handler module so it can
wire them into argparse.  No business logic here — pure registration.
"""

from __future__ import annotations

import argparse

from peerpedia_core.cli.handlers.account import _cmd_register, _cmd_login, _cmd_whoami
from peerpedia_core.cli.handlers.articles import (
    _cmd_article_create, _cmd_article_show, _cmd_article_list,
    _cmd_article_edit, _cmd_article_publish, _cmd_article_delete,
    _cmd_article_scan,
)
from peerpedia_core.cli.handlers.reviews import _cmd_review_submit, _cmd_review_list
from peerpedia_core.cli.handlers.social import (
    _cmd_fork, _cmd_merge_propose, _cmd_merge_accept,
    _cmd_bookmark_add, _cmd_bookmark_list,
)
from peerpedia_core.cli.handlers.compile_ import _cmd_compile
from peerpedia_core.cli.handlers.maintainers import _cmd_maintainer_add, _cmd_maintainer_remove, _cmd_maintainer_list
from peerpedia_core.cli.handlers.sync import _cmd_sync_status, _cmd_sync_push
from peerpedia_core.cli.handlers.mother import _cmd_mother


# TODO(cli-split): split into peerpedia_core/cli/ — each subcommand
# registers itself so build_parser() becomes a table-driven loop.


def _help(func):
    """Extract the first line of a handler's docstring for argparse help text."""
    return (func.__doc__ or "").splitlines()[0].strip()


def _add_common_args(p: argparse.ArgumentParser):
    # --user defaults to None; _resolve_user reads the current user from
    # ~/.peerpedia/session.json when no explicit user is given.
    p.add_argument("--user", default=None, help="User ID (omit to use current session user)")
    p.add_argument("--json", action="store_true", help="Output as JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("peerpedia", description="PeerPedia — peer review from the terminal")
    subs = parser.add_subparsers(dest="command")

    # ── account ──────────────────────────────────────────────────────────

    acct = subs.add_parser("account", help="Account management")
    acct_subs = acct.add_subparsers(dest="subcommand")

    p = acct_subs.add_parser("register", help=_help(_cmd_register))
    p.add_argument("--name", required=True, help="Your display name")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=_cmd_register)

    p = acct_subs.add_parser("login", help=_help(_cmd_login))
    p.add_argument("--name", required=True, help="Your display name")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=_cmd_login)

    p = acct_subs.add_parser("whoami", help=_help(_cmd_whoami))
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=_cmd_whoami)

    # ── article ──────────────────────────────────────────────────────────

    art = subs.add_parser("article", help="Article management")
    art_subs = art.add_subparsers(dest="subcommand")

    p = art_subs.add_parser("create", help=_help(_cmd_article_create))
    p.add_argument("--title", required=True, help="Article title")
    p.add_argument("--format", default="markdown", choices=["markdown", "typst"], help="Source format")
    p.add_argument("--content", help="Article body (inline; omit to open editor)")
    p.add_argument("--no-editor", action="store_true", help="Create empty article without opening editor")
    p.add_argument("--publish", action="store_true", help="Publish immediately after creation")
    p.add_argument("--scores", help='Self-review scores, e.g. "orig=4,rigor=3,comp=4,ped=3,imp=3"')
    _add_common_args(p)
    p.set_defaults(func=_cmd_article_create)

    p = art_subs.add_parser("show", help=_help(_cmd_article_show))
    p.add_argument("id", help="Article ID (or prefix)")
    p.add_argument("--show", choices=["meta", "full", "content"], default="meta",
                   help="What to display: meta (metadata only, default), full (metadata + content), content (source only)")
    _add_common_args(p)
    p.set_defaults(func=_cmd_article_show)

    p = art_subs.add_parser("list", help=_help(_cmd_article_list))
    p.add_argument("--status", choices=["draft", "sedimentation", "published"], help="Filter by status")
    _add_common_args(p)
    p.set_defaults(func=_cmd_article_list)

    p = art_subs.add_parser("edit", help=_help(_cmd_article_edit))
    p.add_argument("id", help="Article ID (or prefix)")
    p.add_argument("--content", help="New article body (omit to open editor)")
    p.add_argument("--title", help="New article title")
    p.add_argument("--no-editor", action="store_true", help="Skip editor; only apply --title if given")
    _add_common_args(p)
    p.set_defaults(func=_cmd_article_edit)

    p = art_subs.add_parser("publish", help=_help(_cmd_article_publish))
    p.add_argument("id", help="Article ID (or prefix)")
    p.add_argument("--scores", required=True, help='Self-review scores, e.g. "orig=4,rigor=3,comp=4,ped=3,imp=3"')
    _add_common_args(p)
    p.set_defaults(func=_cmd_article_publish)

    p = art_subs.add_parser("delete", help=_help(_cmd_article_delete))
    p.add_argument("id", help="Article ID (or prefix)")
    _add_common_args(p)
    p.set_defaults(func=_cmd_article_delete)

    p = art_subs.add_parser("scan", help=_help(_cmd_article_scan))
    p.set_defaults(func=_cmd_article_scan)

    # ── review ───────────────────────────────────────────────────────────

    rev = subs.add_parser("review")
    rev_subs = rev.add_subparsers(dest="subcommand")

    p = rev_subs.add_parser("submit", help=_help(_cmd_review_submit))
    p.add_argument("article_id", help="Article ID (or prefix)")
    p.add_argument("--scores", required=True, help='Five-dim scores, e.g. "orig=4,rigor=3,comp=4,ped=3,imp=3"')
    p.add_argument("--comment", help="Optional review comment")
    _add_common_args(p)
    p.set_defaults(func=_cmd_review_submit)

    p = rev_subs.add_parser("list", help=_help(_cmd_review_list))
    p.add_argument("article_id", help="Article ID (or prefix)")
    p.add_argument("--show", choices=["meta", "full"], default="meta",
                   help="What to display: meta (scores summary, default), full (scores + review threads from git)")
    _add_common_args(p)
    p.set_defaults(func=_cmd_review_list)

    # ── fork ─────────────────────────────────────────────────────────────

    p = subs.add_parser("fork", help=_help(_cmd_fork))
    p.add_argument("article_id", help="Published article ID to fork")
    _add_common_args(p)
    p.set_defaults(func=_cmd_fork)

    # ── merge ────────────────────────────────────────────────────────────

    merge = subs.add_parser("merge")
    merge_subs = merge.add_subparsers(dest="subcommand")

    p = merge_subs.add_parser("propose", help=_help(_cmd_merge_propose))
    p.add_argument("fork_id", help="Your fork's article ID")
    p.add_argument("--target", required=True, help="Original article ID to merge into")
    _add_common_args(p)
    p.set_defaults(func=_cmd_merge_propose)

    p = merge_subs.add_parser("accept", help=_help(_cmd_merge_accept))
    p.add_argument("proposal_id", help="Merge proposal ID")
    p.add_argument("--target", required=True, help="Target article ID")
    _add_common_args(p)
    p.set_defaults(func=_cmd_merge_accept)

    # ── bookmark ─────────────────────────────────────────────────────────

    bm = subs.add_parser("bookmark")
    bm_subs = bm.add_subparsers(dest="subcommand")

    p = bm_subs.add_parser("add", help=_help(_cmd_bookmark_add))
    p.add_argument("article_id", help="Article ID (or prefix)")
    _add_common_args(p)
    p.set_defaults(func=_cmd_bookmark_add)

    p = bm_subs.add_parser("list", help=_help(_cmd_bookmark_list))
    _add_common_args(p)
    p.set_defaults(func=_cmd_bookmark_list)

    # ── compile ──────────────────────────────────────────────────────────

    p = subs.add_parser("compile", help=_help(_cmd_compile))
    p.add_argument("id", help="Article ID (or prefix)")
    p.add_argument("--format", choices=["pdf", "svg", "png", "html"], help="Output format (default: pdf)")
    _add_common_args(p)
    p.set_defaults(func=_cmd_compile)

    # ── sync ─────────────────────────────────────────────────────────────

    sync = subs.add_parser("sync")
    sync_subs = sync.add_subparsers(dest="subcommand")

    p = sync_subs.add_parser("status", help=_help(_cmd_sync_status))
    p.add_argument("--server", help="Peer server URL (or set PEERPEDIA_SERVER env var)")
    p.set_defaults(func=_cmd_sync_status)

    p = sync_subs.add_parser("push", help=_help(_cmd_sync_push))
    p.add_argument("--server", help="Peer server URL (or set PEERPEDIA_SERVER env var)")
    p.set_defaults(func=_cmd_sync_push)

    # TODO(sync): add ``sync pull`` command.
    # TODO(sync): add ``sync discover`` command.

    # ── maintainer ───────────────────────────────────────────────────────

    maintainer = subs.add_parser("maintainer")
    maintainer_subs = maintainer.add_subparsers(dest="subcommand")

    p = maintainer_subs.add_parser("add", help=_help(_cmd_maintainer_add))
    p.add_argument("article_id", help="Article ID")
    p.add_argument("--target-user", required=True, help="User ID to add as maintainer")
    _add_common_args(p)
    p.set_defaults(func=_cmd_maintainer_add)

    p = maintainer_subs.add_parser("remove", help=_help(_cmd_maintainer_remove))
    p.add_argument("article_id", help="Article ID")
    p.add_argument("--target-user", required=True, help="User ID to remove from maintainers")
    _add_common_args(p)
    p.set_defaults(func=_cmd_maintainer_remove)

    p = maintainer_subs.add_parser("list", help=_help(_cmd_maintainer_list))
    p.add_argument("article_id", help="Article ID")
    _add_common_args(p)
    p.set_defaults(func=_cmd_maintainer_list)

    # ── ?Mother — user guide ───────────────────────────────────────────────

    p = subs.add_parser("?Mother", help="Interactive user guide")
    p.set_defaults(func=_cmd_mother)

    return parser
