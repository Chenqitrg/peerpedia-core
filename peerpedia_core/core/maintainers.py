# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Maintainer management — add, remove, consent, and list article maintainers.

Call graph::

    add_maintainer_to_article
      ├► policies._is_maintainer               (caller must be maintainer)
      ├► crud_maintainer.add_maintainer         (insert row)
      └► crud_maintainer.is_maintainer          (pre-check for duplicate)

    remove_maintainer_from_article
      ├► policies._is_maintainer               (caller must be maintainer, or self)
      └► crud_maintainer.remove_maintainer      (delete row)

    consent_to_publish / revoke_publish_consent
      └► crud_article.add_publish_consent / clear_publish_consents

Only existing maintainers can add or remove other maintainers.
Self-removal is allowed as long as there is at least one other maintainer.
Transfer: add(new) + remove(self), always add before remove.
"""

from __future__ import annotations

from peerpedia_core.storage.db import Session

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.storage.db.guards import (
    assert_caller_is_maintainer, guard_not_already_maintainer,
    guard_not_last_maintainer,
    require_article, require_user,
)
from peerpedia_core.storage.db.crud_publish import (
    add_publish_consent, clear_publish_consents, remove_publish_consent,
)
from peerpedia_core.storage.db.models import ArticleMetaStorage
from peerpedia_core.storage.db import crud_maintainer


def add_maintainer_to_article(
    db: Session,
    article_id: str,
    user_id: str,
    caller_id: str,
) -> dict[str, object]:
    """Grant maintainer status to *user_id* for *article_id*.

    Only an existing maintainer (*caller_id*) can add a new maintainer.

    Raises NotFoundError if the user to add is not found.
    Raises ConflictError if the user is already a maintainer.
    """
    assert_caller_is_maintainer(db, article_id, caller_id)
    require_user(db, user_id)

    guard_not_already_maintainer(db, article_id, user_id)
    crud_maintainer.add_maintainer(db, article_id, user_id)
    return {"article_id": article_id, "user_id": user_id, "action": "added"}


def remove_maintainer_from_article(
    db: Session,
    article_id: str,
    user_id: str,
    caller_id: str,
) -> dict[str, object]:
    """Revoke maintainer status from *user_id* for *article_id*.

    An existing maintainer can remove another maintainer.  Self-removal is
    allowed as long as there is at least one other maintainer (orphan
    prevention).

    Raises NotAuthorizedError if caller tries to self-remove as the last maintainer.
    Raises NotFoundError if the target user is not a maintainer.
    """
    assert_caller_is_maintainer(db, article_id, caller_id)
    guard_not_last_maintainer(db, article_id, caller_id, user_id)

    deleted = crud_maintainer.remove_maintainer(db, article_id, user_id)
    if not deleted:
        raise NotFoundError(code="NOT_MAINTAINER_REMOVE")

    return {"article_id": article_id, "user_id": user_id, "action": "removed"}


def list_maintainers(db: Session, article_id: str) -> list[str]:
    """Return maintainer IDs for an article, ordered by created_at.

    Raises NotFoundError if the article is not found.
    """
    article = require_article(db, article_id)
    return crud_maintainer.get_maintainer_ids(db, article_id)


def consent_to_publish(db: Session, article_id: str, user_id: str) -> dict[str, object]:
    """Record a maintainer's consent to publish/merge the article."""
    assert_caller_is_maintainer(db, article_id, user_id)
    add_publish_consent(db, article_id, user_id)
    return {"article_id": article_id, "user_id": user_id, "action": "consented"}


def revoke_publish_consent(db: Session, article_id: str, user_id: str) -> dict[str, object]:
    """Revoke a maintainer's consent to publish/merge.

    Raises NotFoundError if the article is not found.
    """
    assert_caller_is_maintainer(db, article_id, user_id)
    remove_publish_consent(db, article_id, user_id)
    return {"article_id": article_id, "user_id": user_id, "action": "revoked"}
