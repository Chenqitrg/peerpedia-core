# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Command handler adapters — ``(ctx, args: dict) -> AppResult``.

Each handler maps a flat arguments dict onto the typed keyword parameters
expected by ``app/commands/*`` functions.  These are the functions stored
in ``CommandSpec.handler`` — invoked by both CLI and REPL after parsing.
"""

from __future__ import annotations

from typing import Any

from peerpedia_core.app.context import AppContext
from peerpedia_core.app.result import AppResult

from peerpedia_core.app.commands import account as _account
from peerpedia_core.app.commands import article as _article
from peerpedia_core.app.commands import bundle as _bundle
from peerpedia_core.app.commands import fork as _fork
from peerpedia_core.app.commands import maintainer as _maintainer
from peerpedia_core.app.commands import notification as _notify
from peerpedia_core.app.commands import review as _review
from peerpedia_core.app.commands import social as _social


# ── Account ──────────────────────────────────────────────────────────────────

def register(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _account.register(ctx, name=args["name"], password=args["password"])

def login(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _account.login(ctx, name=args["name"], password=args["password"])

def recover(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _account.recover(ctx, name=args.get("name"), user_id=args.get("user_id"),
                            password=args["password"])

def whoami(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _account.whoami(ctx)

def bootstrap(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _account.bootstrap(ctx, from_json=args["from_"], peer=args.get("peer"))

def account_delete(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _account.delete_account(ctx)

def account_search(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _account.search_users(ctx, query=args.get("query", ""))


# ── Article ──────────────────────────────────────────────────────────────────

def article_create(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _article.create(ctx, title=args["title"],
        format=args.get("format", "markdown"),
        content=args.get("content", ""),
        publish=args.get("publish", False),
        scores_str=args.get("scores"))

def article_show(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _article.show(ctx, article_ref=args["id"],
        show=args.get("show", "meta"))

def article_list(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _article.list_articles(ctx,
        search_query=args.get("search"),
        status_arg=args.get("status"),
        mine=args.get("mine"),
        feed=args.get("feed", False),
        bookmarked=args.get("bookmarked", False),
        user_ref=args.get("user"),
        server=args.get("server"),
        limit=int(args.get("limit", 20)))

def article_edit(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _article.edit(ctx, article_ref=args["id"],
        content=args.get("content"),
        title=args.get("title"),
        message=args.get("message", ""))

def article_publish(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _article.publish(ctx, article_ref=args["id"],
        scores_str=args["scores"])

def article_delete(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _article.delete(ctx, article_ref=args["id"])

def article_scan(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _article.scan(ctx)

def article_diff(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _article.diff(ctx, article_ref=args["id"],
        hash1=args.get("hash1"), hash2=args.get("hash2"))


# ── Review ───────────────────────────────────────────────────────────────────

def review_submit(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _review.submit(ctx, article_ref=args["article_id"],
        scores_str=args["scores"], comment=args["comment"])

def review_list(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _review.list_reviews(ctx, article_ref=args["article_id"])

def review_reply(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _review.reply(ctx, article_ref=args["article_id"],
        to_ref=args["to"], content=args.get("content", ""))

def review_invite(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _review.invite_reviewer(ctx, article_ref=args["article_id"],
        user_ref=args["user"])

def review_accept(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _review.accept(ctx, article_ref=args["article_id"])

def review_decline(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _review.decline(ctx, article_ref=args["article_id"])

def review_rate(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _review.rate(ctx, article_ref=args["article_id"],
        reviewer_ref=args["reviewer"], helpfulness=int(args["helpfulness"]))


# ── Merge ────────────────────────────────────────────────────────────────────

def merge_propose(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _fork.merge_propose(ctx, fork_ref=args.get("fork_id"),
        target_ref=args["target"])

def merge_accept(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _fork.merge_accept(ctx, proposal_ref=args.get("proposal_id"),
        target_ref=args["target"])

def merge_withdraw(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _fork.merge_withdraw(ctx, proposal_ref=args.get("proposal_id"))


# ── Social ───────────────────────────────────────────────────────────────────

def follow(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.follow(ctx, target_ref=args["user_identifier"])

def unfollow(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.unfollow(ctx, target_ref=args["user_identifier"])

def following(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.list_following(ctx, user_ref=args["user"])

def followers(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.list_followers(ctx, user_ref=args["user"])

def school(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.school(ctx, limit=int(args.get("limit", 20)),
        local=args.get("local", False), server=args.get("server", ""))

def bookmark_add(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.bookmark(ctx, article_ref=args["article_id"])

def bookmark_remove(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.unbookmark(ctx, article_ref=args["article_id"])

def alias_set(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.alias(ctx, user_ref=args["user_identifier"],
        alias=args["alias"])

def alias_remove(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.unalias(ctx, user_ref=args["user_identifier"])

def alias_list(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.alias_list(ctx)

def share_add(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.share(ctx, article_ref=args["article_id"],
        to_ref=args.get("to"), comment=args.get("comment"))

def share_list(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.share_list(ctx, mine=args.get("mine", False))

def share_remove(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _social.unshare(ctx, article_ref=args["article_id"])


# ── Notifications ────────────────────────────────────────────────────────────

def notifications(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _notify.list_notifications(ctx, unread_only=not args.get("all", False))

def notifications_read(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _notify.mark_read_notification(ctx, notification_id=args["notification_id"])


# ── Sync ─────────────────────────────────────────────────────────────────────

def sync_status(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _bundle.sync_status(ctx, server=args.get("server", ""))

def sync_pull(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _bundle.sync_pull(ctx, server=args.get("server", ""))

def sync_discover(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _bundle.sync_discover(ctx, server=args.get("server", ""),
        depth=int(args.get("depth", 1)),
        max_users=int(args.get("max_users", 100)))


# ── Fork ─────────────────────────────────────────────────────────────────────

def fork(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _fork.fork(ctx, article_ref=args["article_id"])


# ── Maintainer ───────────────────────────────────────────────────────────────

def maintainer_add(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _maintainer.add(ctx, article_ref=args["article_id"],
        target_ref=args["target_user"])

def maintainer_remove(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _maintainer.remove(ctx, article_ref=args["article_id"],
        target_ref=args["target_user"])

def maintainer_list(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _maintainer.list_article_maintainers(ctx, article_ref=args["article_id"])

def maintainer_consent(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _maintainer.consent(ctx, article_ref=args["article_id"])

def maintainer_revoke(ctx: AppContext, args: dict[str, Any]) -> AppResult:
    return _maintainer.revoke(ctx, article_ref=args["article_id"])
