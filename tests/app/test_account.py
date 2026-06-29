# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Account commands."""

import pytest

from peerpedia_core.exceptions import BadRequestError, NotFoundError
from tests.app.conftest import login


class TestRegister:
    def test_register_creates_user(self, ctx):
        from peerpedia_core.app.commands.account import register, whoami
        from peerpedia_core.core import get_user, list_users_by_name
        register(ctx, name="Alice", password="secure123")
        users = list_users_by_name(ctx.db, "Alice")
        assert len(users) == 1
        assert users[0].name == "Alice"

    def test_duplicate_name_rejected(self, ctx):
        from peerpedia_core.app.commands.account import register
        register(ctx, name="Alice", password="p1")
        with pytest.raises(BadRequestError):
            register(ctx, name="Alice", password="p2")


class TestWhoami:
    def test_whoami_logged_in(self, ctx):
        from peerpedia_core.app.commands.account import whoami
        alice = login(ctx, "Alice")
        result = whoami(alice)
        assert result.data["name"] == "Alice"

    def test_whoami_not_logged_in(self, ctx):
        from peerpedia_core.app.commands.account import whoami
        from peerpedia_core.exceptions import NotAuthorizedError
        with pytest.raises(NotAuthorizedError):
            whoami(ctx)


class TestSearchUsers:
    def test_search_finds_user(self, ctx):
        from peerpedia_core.app.commands.account import search_users
        login(ctx, "Alice")
        result = search_users(ctx, query="Ali")
        assert len(result.data["items"]) >= 1


class TestDeleteAccount:
    def test_delete_own_account(self, ctx):
        from peerpedia_core.app.commands.account import delete_account
        from peerpedia_core.core import get_user
        alice = login(ctx, "Alice")
        result = delete_account(alice)
        assert result.code == "ACCOUNT_DELETED"
        # Soft-deleted: still findable by ID
        assert get_user(ctx.db, alice.current_user_id).deleted_at is not None
