# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for cli/decorators.py — @with_context internals."""

from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════════════════════
# _rollback_ctx
# ═══════════════════════════════════════════════════════════════════════════════


class TestRollbackCtx:
    def test_rollbacks_when_db_present(self):
        """ctx with db → session.rollback() is called."""
        from peerpedia_core.cli.decorators import _rollback_ctx

        ctx = MagicMock()
        ctx.db = MagicMock()
        _rollback_ctx(ctx)
        ctx.db.rollback.assert_called_once()

    def test_noop_when_ctx_is_none(self):
        """None ctx → no crash, no side effects."""
        from peerpedia_core.cli.decorators import _rollback_ctx

        _rollback_ctx(None)  # should not raise

    def test_noop_when_db_is_none(self):
        """ctx with db=None → no crash."""
        from peerpedia_core.cli.decorators import _rollback_ctx

        ctx = MagicMock()
        ctx.db = None
        _rollback_ctx(ctx)  # should not raise

    def test_swallows_exceptions(self):
        """Rollback failure → swallowed, never crashes."""
        from peerpedia_core.cli.decorators import _rollback_ctx

        ctx = MagicMock()
        ctx.db = MagicMock()
        ctx.db.rollback.side_effect = RuntimeError("db gone")
        _rollback_ctx(ctx)  # should not raise


# ═══════════════════════════════════════════════════════════════════════════════
# _auto_sync
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutoSync:
    def test_calls_try_sync(self):
        """_auto_sync delegates to _try_sync from bundle_utils (lazy import)."""
        from peerpedia_core.cli.decorators import _auto_sync

        ctx = MagicMock()
        ctx.db = MagicMock()
        # _try_sync is lazily imported from bundle_utils inside _auto_sync
        with patch("peerpedia_core.cli.bundle_utils._try_sync") as mock_sync:
            _auto_sync(ctx)
            mock_sync.assert_called_once_with(ctx.db)

    def test_swallows_exceptions(self):
        """Sync failure → swallowed, never crashes the CLI."""
        from peerpedia_core.cli.decorators import _auto_sync

        ctx = MagicMock()
        ctx.db = MagicMock()
        with patch(
            "peerpedia_core.cli.bundle_utils._try_sync",
            side_effect=ConnectionError("offline"),
        ):
            _auto_sync(ctx)  # should not raise
