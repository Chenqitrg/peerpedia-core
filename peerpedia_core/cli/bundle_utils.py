# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Auto-bundle helpers — thin CLI wrappers over ``app/commands/sync.py``.

Only maps errors to ``_out`` codes.  All sync logic lives in ``core/``.
"""

from __future__ import annotations

import os

from peerpedia_core.cli.session import _get_session_user
from peerpedia_core.cli.info import _out
from peerpedia_core.config.params import PEERPEDIA_SERVER_ENV, params
from peerpedia_core.config.paths import SERVER_DEFAULT_FILE
from peerpedia_core.app.commands.sync import sync_all as _core_sync_all, sync_all_peers as _core_sync_all_peers
from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError
from peerpedia_core.time import validate_clock_skew
from peerpedia_core.transport import Transport

_TRANSPORT = Transport.from_http()
_no_server_warned = False


def _warn_no_server() -> None:
    global _no_server_warned
    if _no_server_warned:
        return
    _no_server_warned = True
    _out(None, "W_NO_KNOWN_PEERS")


def _require_online_server(args) -> str:
    server = _resolve_server_url(args)
    if not _TRANSPORT.is_online(server):
        _out(None, "OFFLINE", server=server)
    skew = _TRANSPORT.check_clock_skew(server)
    err = validate_clock_skew(skew)
    if err:
        _out(args, "CLOCK_SKEW", server=server, error=err)
    return server


# ── Error → message mapping ──────────────────────────────────────────────────


def _map_sync_error(e: Exception) -> str:
    """Return the message code for a sync error, or raise if unknown."""
    if isinstance(e, TransportError):
        return "S_AUTO_SYNC_FAILED"  # caller passes detail=e.detail
    if isinstance(e, ProtocolError):
        return "S_AUTO_SYNC_FAILED"
    if isinstance(e, ConflictError):
        return "S_AUTO_SYNC_CONFLICT"
    raise e  # unexpected — let it propagate


# ── Public API ───────────────────────────────────────────────────────────────


def _resolve_or_skip(server: str | None = None) -> str | None:
    """Resolve server URL.  Return None if offline — caller should skip."""
    srv = server or os.environ.get(PEERPEDIA_SERVER_ENV)
    if not srv:
        _warn_no_server()
        return None
    if not _TRANSPORT.is_online(srv):
        _out(None, "S_AUTO_SYNC_OFFLINE", server=srv)
        return None
    return srv


def _try_sync(db, server: str | None = None) -> None:
    """Sync articles + discover from *server*.  Best-effort: errors are silent."""
    srv = _resolve_or_skip(server)
    if not srv:
        return
    from peerpedia_core.app.commands.sync import sync_and_discover
    sync_and_discover(
        db, _TRANSPORT, srv, user_id=_get_session_user(), pre_check=False,
        on_synced=lambda n: _out(None, "S_SYNCED_COUNT", count=n, server=srv),
        on_discovered=lambda n: _out(None, "S_AUTO_SYNC_DISCOVERED", count=n),
        on_error=lambda e: _out(None, _map_sync_error(e),
                                detail=getattr(e, "detail", str(e))),
    )


def _try_sync_all(db) -> None:
    """Sync articles + discover from every known peer.  Best-effort."""
    _core_sync_all_peers(
        db, _TRANSPORT, user_id=_get_session_user(),
        on_peer_start=lambda srv: _out(None, "S_SYNCED_COUNT", count=0, server=srv),
        on_peer_done=lambda srv, n: _out(None, "S_SYNCED_COUNT", count=n, server=srv),
        on_peer_discover=lambda n: _out(None, "S_AUTO_SYNC_DISCOVERED", count=n),
        on_peer_skip=lambda srv, reason: _out(None, "S_AUTO_SYNC_OFFLINE", server=srv),
        on_peer_error=lambda e: _out(None, _map_sync_error(e),
                                     detail=getattr(e, "detail", str(e))),
    )


# ── Server URL resolution ────────────────────────────────────────────────────



def _resolve_server_url(args) -> str:
    """Resolve peer URL: --server flag → env var → saved default → die."""
    srv = getattr(args, "server", None) or os.environ.get(PEERPEDIA_SERVER_ENV)
    if not srv:
        srv = _read_saved_server()
    if not srv:
        _out(None, "NOT_CONFIGURED")
    if srv:
        _save_default_server(srv)
        _check_stale_server(srv)
    return srv


def _read_saved_server() -> str | None:
    """Read default URL from disk, or None if missing/unreadable."""
    try:
        if SERVER_DEFAULT_FILE.is_file():
            return SERVER_DEFAULT_FILE.read_text().strip()
    except OSError as e:
        _out(None, "CONFIG_ERROR", path=str(SERVER_DEFAULT_FILE), error=str(e))
    return None


_stale_counter: dict[str, int] = {}


def _check_stale_server(url: str) -> None:
    """Warn if *url* has been unreachable for 3+ consecutive calls."""
    if _TRANSPORT.is_online(url):
        _stale_counter.pop(url, None)
        return
    _stale_counter[url] = _stale_counter.get(url, 0) + 1
    if _stale_counter[url] >= params.server.stale_server_warn_after:
        _out(None, "S_STALE_SERVER", server=url)
        _out(None, "S_STALE_SERVER_HINT", path=str(SERVER_DEFAULT_FILE))


def _save_default_server(url: str) -> None:
    """Persist *url* as the default server for future commands."""
    try:
        SERVER_DEFAULT_FILE.parent.mkdir(parents=True, exist_ok=True)
        SERVER_DEFAULT_FILE.write_text(url)
    except OSError as e:
        _out(None, "S_CANNOT_SAVE", path=str(SERVER_DEFAULT_FILE.parent), error=str(e))
