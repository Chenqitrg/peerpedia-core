# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for CitationStorage CRUD."""

import pytest

from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.storage.db.engine import get_session
from tests.crud.conftest import make_article, make_user


class TestCitationCRUD:
    def test_create_and_update(self, engine):
        from peerpedia_core.storage.db.crud_citation import (
            create_or_update_citation, get_cited_by, get_cites,
        )

        session = get_session(engine)
        author = make_user(session, "cit_author")
        a1 = make_article(session, authors=[author.id])
        a2 = make_article(session, authors=[author.id])
        a3 = make_article(session, authors=[author.id])
        create_or_update_citation(session, a1.id, a2.id, forward=0.5, backward=0.2)
        create_or_update_citation(session, a1.id, a3.id, forward=0.3, backward=0.1)
        cites = get_cites(session, a1.id)
        assert len(cites) == 2
        cited_by = get_cited_by(session, a2.id)
        assert len(cited_by) == 1
        assert cited_by[0].from_article_id == a1.id
        session.close()

    def test_update_probabilities(self, engine):
        from peerpedia_core.storage.db.crud_citation import (
            create_or_update_citation, get_citation,
        )

        session = get_session(engine)
        author = make_user(session, "cp_au")
        a1 = make_article(session, authors=[author.id])
        a2 = make_article(session, authors=[author.id])
        create_or_update_citation(session, a1.id, a2.id, forward=0.1, backward=0.1)
        c = get_citation(session, a1.id, a2.id)
        assert c.forward_prob == 0.1
        create_or_update_citation(session, a1.id, a2.id, forward=0.9, backward=0.05)
        c2 = get_citation(session, a1.id, a2.id)
        assert c2.forward_prob == 0.9
        session.close()

    def test_create_or_update_citation_rejects_self_reference(self, engine):
        from peerpedia_core.storage.db.crud_citation import create_or_update_citation

        session = get_session(engine)
        author = make_user(session, "cit_sr")
        a1 = make_article(session, authors=[author.id])
        with pytest.raises(BadRequestError):
            create_or_update_citation(session, a1.id, a1.id)
        session.close()

    def test_get_citations_all_edges(self, engine):
        from peerpedia_core.storage.db.crud_citation import (
            create_or_update_citation, get_citations,
        )

        session = get_session(engine)
        author = make_user(session, "cit_gc")
        a1 = make_article(session, authors=[author.id])
        a2 = make_article(session, authors=[author.id])
        a3 = make_article(session, authors=[author.id])
        create_or_update_citation(session, a1.id, a2.id)
        create_or_update_citation(session, a3.id, a1.id)
        edges = get_citations(session, a1.id)
        assert len(edges) == 2
        session.close()
