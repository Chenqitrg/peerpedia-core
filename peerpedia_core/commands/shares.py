# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Share commands — public recommendations visible to followers.

Shares are public — they propagate to followers and serve as content
discovery and moderation signals.  Unlike bookmarks (private), shares
are pushed to servers and merged during social graph discovery.
"""

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_share import (
    add_share as _add,
    remove_share as _remove,
    get_shares_by_followed as _feed,
    get_shares_for_user as _for_user,
)


def add_share(
    db: Session, sharer_id: str, article_id: str, *,
    recipient_id: str | None = None, comment: str | None = None,
) -> dict:
    s = _add(db, sharer_id, article_id, recipient_id=recipient_id, comment=comment)
    return {"id": s.id, "article_id": s.article_id, "sharer_id": s.sharer_id,
            "recipient_id": s.recipient_id, "comment": s.comment}


def remove_share(db: Session, sharer_id: str, article_id: str) -> None:
    _remove(db, sharer_id, article_id)


def get_shares_for_user(db: Session, user_id: str) -> list[dict]:
    return [
        {"id": s.id, "article_id": s.article_id, "sharer_id": s.sharer_id,
         "comment": s.comment, "created_at": s.created_at.isoformat()}
        for s in _for_user(db, user_id)
    ]


def get_feed_shares(db: Session, viewer_id: str) -> list[dict]:
    articles = _feed(db, viewer_id)
    return [
        {"id": a.id, "title": a.title, "status": a.status} for a in articles
    ]
