# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Review commands — submit and list."""

from __future__ import annotations

from peerpedia_core.cli.helpers import (
    _with_db, _get_session_user, _get_session_key, _open_editor, _parse_scores,
    _page, _resolve_article_id, _resolve_user, _ok, _die, _json_out,
    _output_result, _empty_state, DEFAULT_ARTICLES_DIR,
)
from peerpedia_core.cli.display import _stars, console
from peerpedia_core.cli.bundle_utils import _try_sync
from peerpedia_core.commands import (
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
    article = _resolve_article_id(db, args.article_id)
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
    if args.json:
        _json_out(result)
    else:
        _ok("Review submitted")
        console.print(_stars(scores))


@_with_db
def _cmd_review_list(db, args):
    """List all reviews for an article.

    args: article_id [positional], --show [meta|full], --json
    """
    article = _resolve_article_id(db, args.article_id)
    reviews = get_reviews_for_article(db, article.id)
    if args.json:
        _json_out([{"id": r.id, "reviewer_id": r.reviewer_id, "scores": r.scores} for r in reviews])
        return
    if not reviews:
        _empty_state("No reviews yet.")
        return

    show_mode = getattr(args, "show", "meta")

    # Batch-load reviewers to avoid N+1 queries.
    reviewer_ids = {r.reviewer_id for r in reviews}
    users_by_id = {u.id: u for u in get_users_by_ids(db, reviewer_ids)}

    for r in reviews:
        ts = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "unknown"
        reviewer = users_by_id.get(r.reviewer_id)
        label = reviewer.name if reviewer else r.reviewer_id[:8]
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

    if show_mode == "full":
        rp = DEFAULT_ARTICLES_DIR / args.article_id
        reviews_dir = rp / "reviews"
        if not reviews_dir.is_dir():
            _die(f"DB has reviews but no reviews/ directory on disk for article {args.article_id}")

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
    article = _resolve_article_id(db, args.article_id)

    template = (
        "# Author Reply\n"
        f"# Article: {article.id}\n"
        f"# Replying to: {reviewer_ref}\n"
        "#\n"
        "# Write your reply below. Lines starting with # are ignored.\n"
        "# An empty reply aborts.\n"
        "\n"
    )
    content = _open_editor(template)
    lines = [l for l in content.splitlines() if not l.strip().startswith("#")]
    reply = "\n".join(lines).strip()
    if not reply:
        _die("Aborting: empty reply.")

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


@_with_db
def _cmd_review_invite(db, args):
    """Invite a user to review an article."""
    user_id = _get_session_user()
    target_id = _resolve_user(db, args.user)
    article = _resolve_article_id(db, args.article_id)
    result = invite_reviewer(db, article.id, user_id, target_id)
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        target_name = get_user(db, target_id).name if get_user(db, target_id) else target_id[:8]
        _ok(f"Invited {target_name} to review [accent]{article.id[:8]}[/]")


@_with_db
def _cmd_review_accept(db, args):
    """Accept a pending review invitation."""
    user_id = _get_session_user()
    article = _resolve_article_id(db, args.article_id)
    result = accept_invitation(db, article.id, user_id)
    db.commit()
    _output_result(args, result, f"You accepted the invitation to review [accent]{article.id[:8]}[/]")


@_with_db
def _cmd_review_decline(db, args):
    """Decline a pending review invitation."""
    user_id = _get_session_user()
    article = _resolve_article_id(db, args.article_id)
    result = decline_invitation(db, article.id, user_id)
    db.commit()
    _output_result(args, result, f"You declined the invitation to review [accent]{article.id[:8]}[/]")


@_with_db
def _cmd_review_rate(db, args):
    """Rate a review's helpfulness."""
    user_id = _get_session_user()
    reviewer_id = _resolve_user(db, args.reviewer)
    article = _resolve_article_id(db, args.article_id)
    result = rate_review_helpfulness(
        db, article.id, reviewer_id, user_id, args.helpfulness,
    )
    db.commit()
    reviewer_user = get_user(db, reviewer_id)
    reviewer_name = reviewer_user.name if reviewer_user else reviewer_id[:8]
    if args.json:
        _json_out(result)
    else:
        stars = '★' * args.helpfulness + '☆' * (5 - args.helpfulness)
        _ok(f"Rated review by {reviewer_name}: {stars}")
