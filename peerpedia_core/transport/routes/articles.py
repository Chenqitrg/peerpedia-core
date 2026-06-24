# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article routes — git bundle sync + content + search + history.

Every handler is a thin wrapper: parse HTTP input → delegate to
``bundle/server`` or ``commands/`` → return JSON / binary response.

Route summary (see ``http_server.py`` docstring for the full table)::

    GET  /api/v1/articles/{id}              → _article        metadata
    GET  /api/v1/articles/{id}/head         → _head           git HEAD hash
    GET  /api/v1/articles/{id}/bundle?since=→ _bundle         git bundle bytes
    POST /api/v1/articles/{id}/sync         → _sync           apply bundle
    GET  /api/v1/articles/{id}/ancestor/{h} → _ancestor       is-ancestor probe
    POST /api/v1/articles                   → _push_article   first-time upload
    GET  /api/v1/articles/{id}/repo         → _repo           first-time download
    GET  /api/v1/articles/{id}/history      → _history        commit log
    GET  /api/v1/articles/{id}/source       → _source         markdown/typst text
    GET  /api/v1/search?q=&status=          → _search         article search
"""

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from peerpedia_core.bundle.server import (
    apply_sync,
    check_article_ancestor,
    get_article_bundle,
    get_article_commit_history,
    get_article_head,
    ingest_first_article,
    pack_article_repo_bundle,
    read_article_source_content,
)
from peerpedia_core.commands import (
    get_article_view,
    list_article_views,
)
from peerpedia_core.exceptions import BadRequestError, NotFoundError
from peerpedia_core.transport.shared import _validate_id

MAX_BUNDLE_BYTES = 100 * 1024 * 1024  # 100 MB


# ── Handlers ─────────────────────────────────────────────────────────────


async def _head(request: Request) -> JSONResponse:
    article_id = request.path_params["article_id"]
    _validate_id(article_id, "article_id")
    result = get_article_head(article_id)
    if result is None:
        raise NotFoundError(f"Article '{article_id}' not found")
    return JSONResponse({"hash": result})


async def _bundle(request: Request) -> Response:
    article_id = request.path_params["article_id"]
    _validate_id(article_id, "article_id")
    since_hash = request.query_params.get("since")
    result = get_article_bundle(article_id, since_hash)
    if result is None:
        raise NotFoundError(f"Bundle not available for '{article_id}'")
    return Response(content=result, media_type="application/octet-stream")


async def _sync(request: Request) -> JSONResponse:
    article_id = request.path_params["article_id"]
    _validate_id(article_id, "article_id")

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_BUNDLE_BYTES:
        raise BadRequestError(
            f"Bundle too large: {int(content_length)} bytes "
            f"(max {MAX_BUNDLE_BYTES})"
        )
    bundle_bytes = await request.body()
    db = request.state.db
    new_head = apply_sync(db, article_id, bundle_bytes)
    return JSONResponse({"head": new_head})


async def _ancestor(request: Request) -> JSONResponse:
    article_id = request.path_params["article_id"]
    _validate_id(article_id, "article_id")
    h = request.path_params["hash"]
    result = check_article_ancestor(article_id, h)
    return JSONResponse({"ancestor": result})


async def _push_article_repo(request: Request) -> JSONResponse:
    payload = await request.json()
    article_id = payload.get("id")
    if not article_id:
        raise BadRequestError("Missing required field: 'id'")
    _validate_id(article_id, "id")
    if "repo_bundle" not in payload:
        raise BadRequestError("Missing required field: 'repo_bundle'")
    if not payload["repo_bundle"]:
        raise BadRequestError("Field 'repo_bundle' must not be empty")
    new_head = ingest_first_article(article_id, payload)
    return JSONResponse({"head": new_head}, status_code=201)


async def _article(request: Request) -> JSONResponse:
    """GET /api/v1/articles/{article_id} → article metadata dict, or 404."""
    article_id = request.path_params["article_id"]
    _validate_id(article_id, "article_id")

    db = getattr(request.state, "db", None)
    if db is None:
        raise NotFoundError(f"Article '{article_id}' not found")
    data = get_article_view(db, article_id)
    if data is None:
        raise NotFoundError(f"Article '{article_id}' not found")
    return JSONResponse(data)


async def _history(request: Request) -> JSONResponse:
    """GET /api/v1/articles/{id}/history?max= → commit history."""
    article_id = request.path_params["article_id"]
    _validate_id(article_id, "article_id")
    max_count = min(int(request.query_params.get("max", 50)), 200)
    since = request.query_params.get("since")
    try:
        commits = get_article_commit_history(article_id, max_count=max_count, since_hash=since)
    except ValueError:
        commits = []
    return JSONResponse(commits)


async def _search(request: Request) -> JSONResponse:
    """GET /api/v1/search?q=&status=&limit=&offset= → article list."""
    db = request.state.db
    q = request.query_params.get("q")
    status = request.query_params.get("status")
    limit = min(int(request.query_params.get("limit", 20)), 100)
    offset = int(request.query_params.get("offset", 0))
    return JSONResponse(list_article_views(
        db, search_query=q, status=status, limit=limit, offset=offset,
    ))


async def _source(request: Request) -> JSONResponse:
    """GET /api/v1/articles/{id}/source → article markdown/typst content."""
    article_id = request.path_params["article_id"]
    _validate_id(article_id, "article_id")
    result = read_article_source_content(article_id)
    if result is None:
        raise NotFoundError(f"Article source not found for '{article_id}'")
    content, fmt = result
    return JSONResponse({"content": content, "format": fmt})


async def _repo(request: Request) -> JSONResponse:
    """GET /api/v1/articles/{id}/repo → base64 tar.gz of full git repo."""
    article_id = request.path_params["article_id"]
    _validate_id(article_id, "article_id")
    return JSONResponse({"repo_bundle": pack_article_repo_bundle(article_id)})


# ── Route table ──────────────────────────────────────────────────────────


ROUTES = [
    Route("/api/v1/articles/{article_id}", _article, methods=["GET"]),
    Route("/api/v1/articles/{article_id}/head", _head, methods=["GET"]),
    Route("/api/v1/articles/{article_id}/bundle", _bundle, methods=["GET"]),
    Route("/api/v1/articles/{article_id}/sync", _sync, methods=["POST"]),
    Route("/api/v1/articles/{article_id}/ancestor/{hash}", _ancestor, methods=["GET"]),
    Route("/api/v1/articles/{article_id}/history", _history, methods=["GET"]),
    Route("/api/v1/search", _search, methods=["GET"]),
    Route("/api/v1/articles/{article_id}/source", _source, methods=["GET"]),
    Route("/api/v1/articles/{article_id}/repo", _repo, methods=["GET"]),
    Route("/api/v1/articles", _push_article_repo, methods=["POST"]),
]
