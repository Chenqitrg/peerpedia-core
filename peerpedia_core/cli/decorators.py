# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""``with_context`` — decorator for every CLI command handler.

Each ``_cmd_*`` function in ``cli/cmds/`` is decorated with
``@with_context``.  The decorator provides:

1. **DB session** — opened, auto-committed on success, rolled back on error
2. **AppContext** — constructed from session + transport, injected as ``ctx``
3. **Result rendering** — ``_render_result()`` on success
4. **Error rendering** — ``_render_error()`` on ``PeerpediaError``
5. **Auto-sync** — best-effort peer sync after write commands

No handler opens its own DB or renders its own output — the framework
does it.  Handlers are pure: ``(ctx, args) → AppResult``.
"""

from __future__ import annotations

import functools
import logging

from peerpedia_core.app.context import AppContext, build_context
from peerpedia_core.cli.info import _render_error, _render_result
from peerpedia_core.config.paths import DB_PATH, DB_URL
from peerpedia_core.core import db_session
from peerpedia_core.exceptions import PeerpediaError

_log = logging.getLogger(__name__)


def with_context(func):
    """Decorate a handler to receive ``(ctx: AppContext, args)``.

    Flow::
        mkdir DB dir
        db_session (auto-commit/rollback)
          ├─ build_context(db) → AppContext
          ├─ func(ctx, args)   → AppResult
          └─ _render_result(args, result)
        _auto_sync(ctx)          ← best-effort, after result rendered
        return                   ← success
        except PeerpediaError    → rollback → _render_error(args, e) → exit(1)
        except Exception         → rollback → log → _render_error(INTERNAL_ERROR) → exit(1)
    """
    @functools.wraps(func)
    def wrapper(args):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        ctx: AppContext | None = None
        try:
            with db_session(DB_URL) as db:
                ctx = build_context(db)
                result = func(ctx, args)
                _render_result(args, result)
                _auto_sync(ctx)  # best-effort — logged on failure, never raises
        except PeerpediaError as e:
            _rollback_ctx(ctx)
            _render_error(args, e)
        except Exception as e:
            _rollback_ctx(ctx)
            _log.error("Unhandled exception in %s: %s", func.__name__, e, exc_info=True)
            _render_error(args, PeerpediaError("INTERNAL_ERROR"))
    return wrapper


def _rollback_ctx(ctx: AppContext | None) -> None:
    """Rollback the DB session if *ctx* was initialized before the error."""
    if ctx is None:
        return
    try:
        ctx.db.rollback()
    except Exception:
        _log.debug("Rollback failed (likely no active transaction)", exc_info=True)


def _auto_sync(ctx: AppContext) -> None:
    """Best-effort sync with known peers after a write command."""
    try:
        from peerpedia_core.cli.bundle_utils import _try_sync
        _try_sync(ctx.db)
    except Exception:
        _log.debug("Auto-sync failed", exc_info=True)
