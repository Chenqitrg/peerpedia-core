# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Fork + merge commands."""

import pytest

from peerpedia_core.exceptions import NotAuthorizedError
from tests.app.conftest import login


def _create_article(ctx, title="Test"):
    from peerpedia_core.app.commands.article import create
    return create(ctx, title=title, content="# X")


# ═══════════════════════════════════════════════════════════════════════════════
# Fork
# ═══════════════════════════════════════════════════════════════════════════════


class TestFork:
    def test_fork_returns_forked_code(self, ctx, articles_dir):
        from peerpedia_core.app.commands.fork import fork
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = _create_article(alice)
        # Bob needs to be a maintainer to fork
        add_maintainer(ctx.db, a.data["id"], bob.current_user_id)
        ctx.db.flush()

        result = fork(bob, article_ref=a.data["id"])
        assert result.code == "FORKED"
        assert result.data["forked_from"] == a.data["id"]

    def test_fork_not_maintainer_rejected(self, ctx, articles_dir):
        from peerpedia_core.app.commands.fork import fork
        from peerpedia_core.exceptions import NotAuthorizedError
        alice = login(ctx, "Alice")
        stranger = login(ctx, "Stranger")
        a = _create_article(alice)

        with pytest.raises(NotAuthorizedError):
            fork(stranger, article_ref=a.data["id"])


# ═══════════════════════════════════════════════════════════════════════════════
# Merge
# ═══════════════════════════════════════════════════════════════════════════════


class TestMerge:
    def test_propose_and_withdraw(self, ctx, articles_dir):
        from peerpedia_core.app.commands.fork import fork, merge_propose, merge_withdraw
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = _create_article(alice)
        add_maintainer(ctx.db, a.data["id"], bob.current_user_id)
        ctx.db.flush()
        f = fork(bob, article_ref=a.data["id"])

        mp = merge_propose(bob, fork_ref=f.data["id"], target_ref=a.data["id"])
        assert mp.code == "MERGE_PROPOSED"

        wd = merge_withdraw(bob, proposal_ref=mp.data["id"])
        assert wd.code == "MERGE_WITHDRAWN"
