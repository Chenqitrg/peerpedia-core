# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Publish consent CRUD — maintainer co-author consent tracking.

Callers must validate article existence via ``require_article``
before calling ``add_publish_consent`` or ``remove_publish_consent``.

Functions
---------
  add_publish_consent       Record a maintainer's consent to publish/merge
  remove_publish_consent    Remove a single maintainer's consent
  clear_publish_consents    Clear all consents (e.g. after content edit)
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import ArticleMetaStorage


def add_publish_consent(session: Session, article: ArticleMetaStorage, user_id: str) -> None:
    """Record a maintainer's consent to publish/merge.

    Appends *user_id* to ``publish_consents`` if not already present.
    """
    consents = list(article.publish_consents or [])
    if user_id not in consents:
        consents.append(user_id)
        article.publish_consents = consents
    session.flush()


def remove_publish_consent(session: Session, article: ArticleMetaStorage, user_id: str) -> None:
    """Remove a single maintainer's consent to publish/merge.

    No-op if the consent was not recorded.
    """
    consents = list(article.publish_consents or [])
    if user_id in consents:
        consents.remove(user_id)
        article.publish_consents = consents if consents else None
    session.flush()


def clear_publish_consents(session: Session, article_id: str) -> None:
    """Clear all publish consents via targeted UPDATE (no load needed)."""
    session.query(ArticleMetaStorage).filter(ArticleMetaStorage.id == article_id).update(
        {"publish_consents": None}, synchronize_session="fetch",
    )
    session.expire_all()
