# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Pure authorization rules — zero IO, zero DB/git dependencies.

Every function takes pre-fetched data and either returns or raises.
Importable from anywhere without circular-dependency risk.
"""

from peerpedia_core.rules.articles import (
    PUBLIC_READABLE_STATUSES,
    assert_article_has_score,
    assert_can_accept_merge,
    assert_can_delete_article,
    assert_can_edit_article,
    assert_can_fork_article,
    assert_can_publish_article,
    assert_can_reply_to_review,
    assert_can_rollback_article,
    assert_can_submit_review,
    assert_not_folded,
    visible_statuses_for_user,
)
from peerpedia_core.rules.reviews import (
    assert_valid_review,
)
