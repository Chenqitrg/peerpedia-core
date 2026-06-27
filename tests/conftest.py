# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared fixtures for core tests."""

import tempfile
from pathlib import Path

import pytest

from peerpedia_core.crypto import derive_key_pair, new_salt, write_key_to_tempfile
from peerpedia_core.storage.db.engine import Base, get_engine, init_db

_TEST_PASSWORD = "test-password-123"


@pytest.fixture
def db_url():
    """Create a temporary SQLite database and return its URL."""
    with tempfile.TemporaryDirectory() as tmp:
        url = f"sqlite:///{tmp}/test.db"
        yield url


@pytest.fixture
def engine(db_url):
    """Create a fresh SQLAlchemy engine with a temporary database."""
    eng = get_engine(db_url)
    Base.metadata.drop_all(eng)  # ensure clean slate
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_engine(engine):
    """Alias for `engine` — used by policy and exception tests."""
    return engine


@pytest.fixture
def test_keypair():
    """Derive a deterministic Ed25519 key pair for test signing.

    Returns (private_key_bytes, pubkey_hex).
    """
    salt = new_salt()
    priv, pub = derive_key_pair(_TEST_PASSWORD, salt)
    return priv, pub.hex()


@pytest.fixture
def test_signing_key_bytes(test_keypair):
    """Ed25519 private key bytes for passing to command functions."""
    priv, _ = test_keypair
    return priv


@pytest.fixture
def test_pubkey_hex(test_keypair):
    """Ed25519 pubkey hex matching test_signing_key_bytes."""
    _, pub = test_keypair
    return pub


def commit_article_signed(repo_path, message, author_name, author_email):
    """Wrap ``commit_article`` with auto-derived test signing keys.

    Uses a fixed test password + deterministic salt (hash of author_email)
    so the same author always signs with the same key — matching production
    behaviour where keys are derived from password + stored salt.

    NOT a fallback — test infrastructure.  Production ``commit_article`` still
    requires explicit *signing_key* and *pubkey_hex*.

    NOTE: the deterministic salt bypasses the production salt storage path
    (new_salt() → DB store → DB retrieve → derive_key_pair).  This helper
    is fine for git-level tests, but tests that need the full auth flow
    should use the fixtures in ``test_crud.py::TestSaltRoundtrip``.
    """
    import hashlib

    from peerpedia_core.storage.git import commit_article

    salt = hashlib.sha256(author_email.encode()).hexdigest()[:32]
    priv_bytes, pub_bytes = derive_key_pair(_TEST_PASSWORD, salt)
    pubkey_hex = pub_bytes.hex()
    key_path = write_key_to_tempfile(priv_bytes)
    try:
        return commit_article(repo_path, message, author_name, author_email,
                             signing_key=key_path, pubkey_hex=pubkey_hex)
    finally:
        key_path.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def _clean_article_repos():
    """Remove stale article repos from ``DEFAULT_ARTICLES_DIR`` before each test.

    Tests share a single articles directory; left-over repos from aborted
    runs would cause spurious "nothing to commit" failures after
    ``init_article_repo`` became idempotent.
    """
    import shutil

    from peerpedia_core.config.paths import ARTICLES_DIR

    articles_dir = Path(ARTICLES_DIR)
    if articles_dir.is_dir():
        for d in articles_dir.iterdir():
            if d.is_dir() and (d / ".git").is_dir():
                shutil.rmtree(str(d))


@pytest.fixture(autouse=True)
def _isolate_health_cache(monkeypatch, tmp_path):
    """Redirect the health-check file cache to a temp directory.

    Without this, tests that call ``is_online()`` or ``check_clock_skew()``
    would write to the real ``~/.peerpedia/server_health.json``, potentially
    deleting or corrupting the user's production health cache.
    """
    monkeypatch.setattr(
        "peerpedia_core.server.http.health._CACHE_FILE",
        tmp_path / "server_health.json",
    )
    monkeypatch.setattr(
        "peerpedia_core.server.http.health._DATA_ROOT",
        tmp_path,
    )
    from peerpedia_core.server.http.health import clear_health_cache
    clear_health_cache()
