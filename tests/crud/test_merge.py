# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for MergeProposalStorage CRUD."""

import pytest

from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.storage.db.engine import get_session
from tests.crud.conftest import make_article, make_user


class TestMergeProposalCRUD:
    def test_create_and_get(self, engine):
        from peerpedia_core.storage.db.crud_merge import (
            create_merge_proposal, get_merge_proposal, get_merge_proposals_for_article,
        )

        session = get_session(engine)
        author = make_user(session, "mp_author")
        forker = make_user(session, "mp_forker")
        original = make_article(session, authors=[author.id])
        fork = make_article(session, authors=[forker.id])
        mp = create_merge_proposal(session, fork_id=fork.id, target_id=original.id, proposer_id=forker.id)
        assert mp.status == "open"
        assert get_merge_proposal(session, mp.id).proposer_id == forker.id
        proposals = get_merge_proposals_for_article(session, original.id)
        assert len(proposals) == 1
        session.close()

    def test_accept_reject(self, engine):
        from peerpedia_core.storage.db.crud_merge import (
            accept_merge_proposal, create_merge_proposal, get_merge_proposal,
        )

        session = get_session(engine)
        author = make_user(session, "mp_a2")
        forker = make_user(session, "mp_f2")
        original = make_article(session, authors=[author.id])
        fork = make_article(session, authors=[forker.id])
        mp = create_merge_proposal(session, fork_id=fork.id, target_id=original.id, proposer_id=forker.id)
        accept_merge_proposal(session, mp.id)
        assert get_merge_proposal(session, mp.id).status == "accepted"
        with pytest.raises(BadRequestError):
            accept_merge_proposal(session, mp.id)
        session.close()

    def test_create_merge_proposal_rejects_self(self, engine):
        from peerpedia_core.storage.db.crud_merge import create_merge_proposal

        session = get_session(engine)
        author = make_user(session, "mp_sr")
        article = make_article(session, authors=[author.id])
        with pytest.raises(BadRequestError, match="CANNOT_SELF_ACTION"):
            create_merge_proposal(session, fork_id=article.id, target_id=article.id, proposer_id=author.id)
        session.close()


class TestMergeErrorPaths:
    def test_resolve_merge_not_found(self, engine):
        from peerpedia_core.storage.db.crud_merge import _resolve

        session = get_session(engine)
        with pytest.raises(ValueError):
            _resolve(session, "no-such-id", "accepted")
        session.close()

    def test_add_merge_thread_message_not_found(self, engine):
        """Merge thread messages now live in git — covered by review thread."""
        pass
