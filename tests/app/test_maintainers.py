# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Maintainer + notification commands."""

from tests.app.conftest import login


def _create_article(ctx, title="Test"):
    from peerpedia_core.app.commands.article import create
    return create(ctx, title=title, content="# X")


# ═══════════════════════════════════════════════════════════════════════════════
# Maintainers
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaintainers:
    def test_list_after_create(self, ctx, articles_dir):
        from peerpedia_core.app.commands.maintainer import list_article_maintainers
        alice = login(ctx, "Alice")
        a = _create_article(alice)
        result = list_article_maintainers(alice, article_ref=a.data["id"])
        mids = result.data["maintainers"]
        assert alice.current_user_id in mids
        assert len(mids) == 1

    def test_consent_and_revoke(self, ctx, articles_dir):
        from peerpedia_core.app.commands.maintainer import consent, revoke
        alice = login(ctx, "Alice")
        a = _create_article(alice)

        r = consent(alice, article_ref=a.data["id"])
        assert r.code == "OK"

        r = revoke(alice, article_ref=a.data["id"])
        assert r.code == "OK"


