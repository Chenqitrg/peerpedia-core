# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared test fixtures for CLI command unit tests."""

from __future__ import annotations

from argparse import Namespace
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from peerpedia_core.app.context import AppContext
from peerpedia_core.transport import Transport


@pytest.fixture
def ctx() -> MagicMock:
    """Mock AppContext — handlers receive this via @with_context."""
    mock = MagicMock(spec=AppContext)
    mock.db = MagicMock()
    mock.transport = MagicMock(spec=Transport)
    return mock


def call(handler, ctx: MagicMock, args: Namespace):
    """Invoke a handler directly, bypassing @with_context.

    ``@with_context`` is framework plumbing (DB open, render, sync).
    Unit tests call the inner function with a mock *ctx* to verify
    delegation logic.
    """
    return handler.__wrapped__(ctx, args)


@contextmanager
def mock_cmd(module_path: str, attr: str):
    """Patch ``attr`` in *module_path* and yield the mock.

    Handlers import app modules at module level under an alias
    (e.g. ``import ...account as _account``).  To intercept those
    calls, patch the alias in the handler module's namespace::

        with mock_cmd('peerpedia_core.cli.cmds.account', '_account') as app:
            call(_cmd_account_register, ctx, Namespace(name='Alice'))
            app.register.assert_called_once()
    """
    target = f'{module_path}.{attr}'
    with patch(target, autospec=True) as mock:
        yield mock
