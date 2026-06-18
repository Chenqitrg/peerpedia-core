# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for the PeerpediaError → HTTP status code mapping.

The actual handler lives in ``backend/peerpedia_api/main.py`` but the
mapping logic is self-contained and testable without the full app.
"""

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from peerpedia_core.exceptions import (
    BadRequestError,
    ConflictError,
    NotAuthorizedError,
    NotFoundError,
    PeerpediaError,
)


@pytest.fixture
def test_app() -> FastAPI:
    """Minimal FastAPI app with the same exception handler as main.py."""
    app = FastAPI()

    _http_status_by_exception: list[tuple[type[PeerpediaError], int]] = [
        (NotFoundError, 404),
        (NotAuthorizedError, 403),
        (ConflictError, 409),
        (BadRequestError, 400),
    ]

    @app.exception_handler(PeerpediaError)
    async def handler(request, exc):
        for exc_type, status in _http_status_by_exception:
            if isinstance(exc, exc_type):
                return JSONResponse(status_code=status, content={"detail": exc.detail})
        return JSONResponse(status_code=500, content={"detail": exc.detail})

    @app.get("/raise/{kind}")
    async def raise_error(kind: str):
        mapping = {
            "not_found": NotFoundError("missing"),
            "not_authorized": NotAuthorizedError("denied"),
            "conflict": ConflictError("duplicate"),
            "bad_request": BadRequestError("invalid"),
            "unknown": type("UnknownError", (PeerpediaError,), {})("weird"),
            "subclass": type("ArticleGoneError", (NotFoundError,), {})("article was removed"),
        }
        raise mapping.get(kind, PeerpediaError("base"))

    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    return TestClient(test_app)


class TestPeerpediaErrorHandler:
    def test_not_found_maps_to_404(self, client):
        r = client.get("/raise/not_found")
        assert r.status_code == 404
        assert r.json()["detail"] == "missing"

    def test_not_authorized_maps_to_403(self, client):
        r = client.get("/raise/not_authorized")
        assert r.status_code == 403
        assert r.json()["detail"] == "denied"

    def test_conflict_maps_to_409(self, client):
        r = client.get("/raise/conflict")
        assert r.status_code == 409
        assert r.json()["detail"] == "duplicate"

    def test_bad_request_maps_to_400(self, client):
        r = client.get("/raise/bad_request")
        assert r.status_code == 400
        assert r.json()["detail"] == "invalid"

    def test_unknown_subclass_maps_to_500(self, client):
        r = client.get("/raise/unknown")
        assert r.status_code == 500

    def test_base_peerpedia_error_maps_to_500(self, client):
        r = client.get("/raise/base")
        assert r.status_code == 500
        assert r.json()["detail"] == "base"

    def test_subclass_uses_isinstance_not_exact_type(self, client):
        """A subclass of NotFoundError must map to 404, not 500.

        Uses isinstance, not type(exc) dict lookup — a subclass of
        NotFoundError inherits the 404 mapping.
        """
        r = client.get("/raise/subclass")
        assert r.status_code == 404
