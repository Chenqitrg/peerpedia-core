# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Auto-bundle helpers — push/pull all local articles after state changes.

Layer 1 of the CLI package.  Imports from ``helpers`` (Layer 1 sibling).
Does NOT import from handlers or parser.
"""

from __future__ import annotations

import os

from peerpedia_core.cli.helpers import DEFAULT_ARTICLES_DIR, _out, _get_session_user
from peerpedia_core.config.paths import DATA_ROOT
from peerpedia_core.core.sync_article import sync_article
from peerpedia_core.core.sync_social import discover_articles
from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError
from peerpedia_core.storage.peers import get_known_peers, record_peer_result
from peerpedia_core.time import validate_clock_skew
from peerpedia_core.transport import Transport

_TRANSPORT = Transport.from_http()
_no_server_warned = False


def _warn_no_server() -> None:
    """Warn once per process that PEERPEDIA_SERVER is not set."""
    global _no_server_warned
    if _no_server_warned:
        return
    _no_server_warned = True
    _out(None, "W_NO_KNOWN_PEERS")


def _require_online_server(args) -> str:
    """Resolve server URL, ensure it's online, check clock skew, die if not."""
    server = _resolve_server_url(args)
    if not _TRANSPORT.is_online(server):
        _out(None, "OFFLINE", server=server)
    skew = _TRANSPORT.check_clock_skew(server)
    err = validate_clock_skew(skew)
    if err:
        _die_clockskew(err, server)
    return server


def _die_clockskew(err: str, server: str):
    """Exit with clock skew error.  Keep as helper — message is dynamic."""
    from peerpedia_core.cli.helpers import _die
    _die(f"{err} with {server}. Fix your system clock before syncing — "
         "commit timestamps would be unreliable for priority claims.",
         code="BAD_REQUEST")


def _sync_articles_to_peer(db, server: str, *, pre_check: bool = True) -> int:
    """Sync local articles to *server*.  Returns count of synced articles."""
    synced = 0
    for article_dir in DEFAULT_ARTICLES_DIR.iterdir():
        if not (article_dir / ".git").is_dir():
            continue
        article_id = article_dir.name
        if pre_check:
            try:
                if _TRANSPORT.fetch_head(server, article_id) is None:
                    continue
            except (TransportError, ProtocolError, ConflictError, ConnectionError):
                continue
        try:
            result = sync_article(db, _TRANSPORT, server, article_id)
            if result["synced"]:
                db.commit()
                synced += 1
        except (TransportError, ProtocolError, ConflictError, ConnectionError):
            continue
    return synced


def _try_sync(db, server: str | None = None) -> None:
    """Sync all local articles with the server if online.  No-op otherwise.

    Best-effort: network and conflict errors are silent — local state
    is already persisted and manual push can retry later.
    """
    srv = server or os.environ.get("PEERPEDIA_SERVER")
    if not srv:
        _warn_no_server()
        return
    if not _TRANSPORT.is_online(srv):
        _out(None, "S_AUTO_SYNC_OFFLINE", server=srv)
        return
    try:
        _sync_articles_to_peer(db, srv, pre_check=False)
        user_id = _get_session_user()
        n = discover_articles(db, _TRANSPORT, srv, user_id)
        if n:
            _out(None, "S_AUTO_SYNC_DISCOVERED", count=n)
    except TransportError as e:
        _out(None, "S_AUTO_SYNC_FAILED", reason="network", detail=e.detail)
    except ProtocolError as e:
        _out(None, "S_AUTO_SYNC_FAILED", reason="protocol", detail=e.detail)
    except ConflictError:
        _out(None, "S_AUTO_SYNC_CONFLICT")
    except ConnectionError as e:
        _out(None, "S_AUTO_SYNC_FAILED", reason="connection", detail=str(e))


def _try_sync_all(db) -> None:
    """Sync all local articles with every known peer.  Best-effort."""
    peers = get_known_peers()
    if not peers:
        _out(None, "S_NO_KNOWN_PEERS")
        return
    for server in peers:
        _try_sync_to_peer(db, server)


def _try_sync_to_peer(db, server: str) -> None:
    """Sync articles + discover new content from *server*.  Best-effort."""
    if not _TRANSPORT.is_online(server):
        record_peer_result(server, success=False)
        return

    skew = _TRANSPORT.check_clock_skew(server)
    if validate_clock_skew(skew):
        _out(None, "S_CLOCK_SKEW_SKIP", skew=skew, server=server)
        record_peer_result(server, success=False)
        return

    try:
        synced = _sync_articles_to_peer(db, server, pre_check=True)
        try:
            user_id = _get_session_user()
            n = discover_articles(db, _TRANSPORT, server, user_id)
            if n:
                _out(None, "S_DISCOVERED_FROM", server=server, count=n)
        except (TransportError, ProtocolError, ConflictError, ConnectionError):
            pass
        if synced:
            _out(None, "S_SYNCED_COUNT", count=synced, server=server)
        record_peer_result(server, success=True)
    except (TransportError, ProtocolError, ConflictError, ConnectionError):
        record_peer_result(server, success=False)


def _resolve_server_url(args) -> str:
    """Return the peer server URL from --server flag, env var, or saved default."""
    srv = getattr(args, "server", None) or os.environ.get("PEERPEDIA_SERVER")
    if not srv:
        default_file = DATA_ROOT / "server_default"
        try:
            if default_file.is_file():
                srv = default_file.read_text().strip()
        except OSError as e:
            _out(None, "CONFIG_ERROR", path=str(default_file), error=str(e))
    if not srv:
        _out(None, "NOT_CONFIGURED")

    default_file = DATA_ROOT / "server_default"
    if not default_file.is_file() or default_file.read_text().strip() != srv:
        _save_default_server(srv)

    if not _TRANSPORT.is_online(srv):
        _stale_hits = _stale_counter.get(srv, 0) + 1
        _stale_counter[srv] = _stale_hits
        if _stale_hits == 3:
            _out(None, "S_STALE_SERVER", server=srv)
            _out(None, "S_STALE_SERVER_HINT", path=str(DATA_ROOT / "server_default"))
    else:
        _stale_counter.pop(srv, None)

    return srv


_stale_counter: dict[str, int] = {}


def _save_default_server(url: str) -> None:
    """Persist *url* as the default server for future commands."""
    try:
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        (DATA_ROOT / "server_default").write_text(url)
    except OSError as e:
        _out(None, "S_CANNOT_SAVE", path=str(DATA_ROOT), error=str(e))
