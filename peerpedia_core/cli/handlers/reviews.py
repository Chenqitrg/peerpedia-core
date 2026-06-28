# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Review commands — submit and list."""

from __future__ import annotations

from peerpedia_core.cli.helpers import (
    _with_db, _get_session_user, _get_session_key, _open_editor, _parse_scores,
    _page, _resolve_user, _ok, _json_out,
    _output_result, _out, DEFAULT_ARTICLES_DIR,
    search_articles,
)
from peerpedia_core.cli.display import _stars, console
from peerpedia_core.types import short_id
from peerpedia_core.cli.bundle_utils import _try_sync
from peerpedia_core.core import (
    accept_invitation, decline_invitation,
    get_reviews_for_article, get_user, get_users_by_ids,
    invite_reviewer, rate_review_helpfulness,
    submit_reply, submit_review,
)


@_with_db
def _cmd_review_submit(db, args):
    """Submit a review with 5-dim scores + optional comment.

    args: article_id [positional], --scores, --comment, --json
    """
    scores = _parse_scores(args.scores)
    reviewer_id = _get_session_user()
    # FIXME: args.article_id is a known ID, should use get_article(db, args.article_id).
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]
    key_bytes = _get_session_key()
    user = get_user(db, reviewer_id)
    result = submit_review(
        db, article_id=article.id, reviewer_id=reviewer_id,
        scores=scores,
        comment=args.comment or "",
        signing_key_bytes=key_bytes,
        pubkey_hex=user.public_key if user else None,
    )
    db.commit()
    _try_sync(db)
    _out(args, "REVIEW_SUBMITTED", result)
    if not args.json:
        console.print(_stars(scores))


@_with_db
def _cmd_review_list(db, args):
    """List all reviews for an article.

    args: article_id [positional], --show [meta|full], --json
    """
    # FIXME: args.article_id is a known ID, should use get_article(db, args.article_id).
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]
    reviews = get_reviews_for_article(db, article.id)
    if args.json:
        _json_out([{"id": r.id, "reviewer_id": r.reviewer_id, "scores": r.scores} for r in reviews])
        return
    if not reviews:
        _out(args, "EMPTY_REVIEWS")
        return

    show_mode = getattr(args, "show", "meta")
    reviewer_ids = {r.reviewer_id for r in reviews}
    users_by_id = {u.id: u for u in get_users_by_ids(db, reviewer_ids)}

    for r in reviews:
        _display_review_card(r, users_by_id)

    if show_mode == "full":
        _display_review_threads(args.article_id)


# ── ReviewMetaStorage display helpers ──────────────────────────────────────────────────


def _display_review_card(r, users_by_id: dict) -> None:
    """Print one review's metadata: reviewer name, timestamp, scores/status."""
    ts = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "unknown"
    reviewer = users_by_id.get(r.reviewer_id)
    label = reviewer.name if reviewer else short_id(r.reviewer_id)
    if r.status == "submitted":
        score_display = _stars(r.scores)
    elif r.status == "accepted":
        score_display = "[warning]accepted[/]"
    elif r.status == "declined":
        score_display = "[error]declined[/]"
    else:
        score_display = "[muted]invited[/]"
    console.print(f"[bold]{label}[/]  [muted]{ts}[/]  {score_display}")
    console.print()


def _display_review_threads(article_id: str) -> None:
    """Page through all review thread markdown files on disk."""
    rp = DEFAULT_ARTICLES_DIR / article_id
    reviews_dir = rp / "reviews"
    if not reviews_dir.is_dir():
        _out(None, "REVIEW_DIR_ERROR", article_id=article_id)

    parts: list[str] = []
    for reviewer_dir in sorted(reviews_dir.iterdir()):
        threads_dir = reviewer_dir / "threads"
        for tf in sorted(threads_dir.glob("*.md")):
            parts.append(tf.read_text())
            parts.append("")
    if parts:
        _page("\n".join(parts))
    else:
        console.print("[muted]No review threads found.[/]")


@_with_db
def _cmd_review_reply(db, args):
    """Reply to a reviewer on an article.  Opens $EDITOR for the reply.

    args: article_id [positional], --to, --json
    """
    user_id = _get_session_user()
    reviewer_ref = _resolve_user(db, args.to)
    # FIXME: args.article_id is a known ID, should use get_article(db, args.article_id).
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]

    template = _build_reply_template(article.id, reviewer_ref)
    reply = _get_reply_from_editor(template)
    if not reply:
        _out(args, "EMPTY_REPLY")

    key_bytes = _get_session_key()
    user = get_user(db, user_id)
    result = submit_reply(
        db, article_id=article.id, user_id=user_id,
        reviewer_ref=reviewer_ref, content=reply,
        signing_key_bytes=key_bytes,
        pubkey_hex=user.public_key if user else None,
    )
    db.commit()
    _output_result(args, result, "Reply posted to review thread")


def _build_reply_template(article_id: str, reviewer_ref: str) -> str:
    """Return the editor template for a review reply."""
    return (
        "# Author Reply\n"
        f"# ArticleMetaStorage: {article_id}\n"
        f"# Replying to: {reviewer_ref}\n"
        "#\n"
        "# Write your reply below. Lines starting with # are ignored.\n"
        "# An empty reply aborts.\n"
        "\n"
    )


def _get_reply_from_editor(template: str) -> str:
    """Open $EDITOR and return the non-comment reply text, or empty string."""
    content = _open_editor(template)
    lines = [l for l in content.splitlines() if not l.strip().startswith("#")]
    return "\n".join(lines).strip()


@_with_db
def _cmd_review_invite(db, args):
    """Invite a user to review an article."""
    user_id = _get_session_user()
    target_id = _resolve_user(db, args.user)
    # FIXME: args.article_id is a known ID, should use get_article(db, args.article_id).
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]
    result = invite_reviewer(db, article.id, user_id, target_id)
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        target_name = get_user(db, target_id).name if get_user(db, target_id) else short_id(target_id)
        _ok(f"Invited {target_name} to review [accent]{short_id(article.id)}[/]")


@_with_db
def _cmd_review_accept(db, args):
    """Accept a pending review invitation."""
    user_id = _get_session_user()
    # FIXME: args.article_id is a known ID, should use get_article(db, args.article_id).
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]
    result = accept_invitation(db, article.id, user_id)
    db.commit()
    _output_result(args, result, f"You accepted the invitation to review [accent]{short_id(article.id)}[/]")


@_with_db
def _cmd_review_decline(db, args):
    """Decline a pending review invitation."""
    user_id = _get_session_user()
    # FIXME: args.article_id is a known ID, should use get_article(db, args.article_id).
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]
    result = decline_invitation(db, article.id, user_id)
    db.commit()
    _output_result(args, result, f"You declined the invitation to review [accent]{short_id(article.id)}[/]")


@_with_db
def _cmd_review_rate(db, args):
    """Rate a review's helpfulness."""
    user_id = _get_session_user()
    reviewer_id = _resolve_user(db, args.reviewer)
    # FIXME: args.article_id is a known ID, should use get_article(db, args.article_id).
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]
    result = rate_review_helpfulness(
        db, article.id, reviewer_id, user_id, args.helpfulness,
    )
    db.commit()
    reviewer_user = get_user(db, reviewer_id)
    reviewer_name = reviewer_user.name if reviewer_user else short_id(reviewer_id)
    if args.json:
        _json_out(result)
    else:
        stars = '★' * args.helpfulness + '☆' * (5 - args.helpfulness)
        _ok(f"Rated review by {reviewer_name}: {stars}")
