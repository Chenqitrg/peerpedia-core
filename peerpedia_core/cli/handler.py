# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Unified handler decorator — the single framework for all CLI commands."""

from __future__ import annotations

import functools
import logging

from peerpedia_core.app.context import AppContext, build_context
from peerpedia_core.cli.output import _render_error, _render_result, _set_die_json_mode
from peerpedia_core.config.paths import DB_PATH, DB_URL
from peerpedia_core.core import db_session
from peerpedia_core.exceptions import PeerpediaError

_log = logging.getLogger(__name__)


def with_context(func):
    """Decorate a handler to receive ``(ctx: AppContext, args)``.

    Opens DB → builds context → calls handler → auto-sync → renders result.
    Catches ``PeerpediaError`` and renders via ``_render_error``.
    """
    @functools.wraps(func)
    def wrapper(args):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _set_die_json_mode(getattr(args, "json", False))
        ctx: AppContext | None = None
        try:
            with db_session(DB_URL) as db:
                ctx = build_context(db)
                result = func(ctx, args)
                _auto_sync(ctx)
                _render_result(args, result)
        except PeerpediaError as e:
            if ctx is not None and hasattr(ctx, "db"):
                _safe_rollback(ctx.db)
            _render_error(args, e)
        except Exception as e:
            if ctx is not None and hasattr(ctx, "db"):
                _safe_rollback(ctx.db)
            _log.error("Unhandled exception in %s: %s", func.__name__, e, exc_info=True)
            _render_error(args, PeerpediaError("INTERNAL_ERROR"))
        finally:
            _set_die_json_mode(False)
    return wrapper


def _safe_rollback(db) -> None:
    try:
        db.rollback()
    except Exception:
        _log.debug("Rollback failed (likely no active transaction)", exc_info=True)


def _auto_sync(ctx: AppContext) -> None:
    """Best-effort sync with known peers after a write command."""
    try:
        from peerpedia_core.cli.bundle_utils import _try_sync
        _try_sync(ctx.db)
    except Exception:
        _log.debug("Auto-sync failed", exc_info=True)
