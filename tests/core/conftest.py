# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared fixtures for core spec tests."""

import hashlib
import tempfile
from pathlib import Path

import pytest

import peerpedia_core.storage.db.models  # noqa: F401 — register all ORM models
from peerpedia_core.crypto import derive_key_pair, write_key_to_tempfile
from peerpedia_core.storage.db.engine import Base, get_engine, get_session

_TEST_PASSWORD = "test-password-123"


@pytest.fixture
def engine():
    with tempfile.TemporaryDirectory() as tmp:
        eng = get_engine(f"sqlite:///{tmp}/test.db")
        Base.metadata.create_all(eng)
        yield eng


@pytest.fixture
def db(engine):
    s = get_session(engine)
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def articles_dir():
    """Override PEERPEDIA_HOME with a temp directory so all article repos
    are created in a temp dir instead of ``~/.peerpedia``."""
    import os
    import peerpedia_core.config.paths as paths_mod
    orig_home = os.environ.get("PEERPEDIA_HOME")
    orig_data = paths_mod.DATA_ROOT
    orig_articles = paths_mod.ARTICLES_DIR
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        os.environ["PEERPEDIA_HOME"] = str(base)
        paths_mod.DATA_ROOT = base / ".peerpedia"
        paths_mod.ARTICLES_DIR = paths_mod.DATA_ROOT / "articles"
        paths_mod.ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
        yield base
        if orig_home is not None:
            os.environ["PEERPEDIA_HOME"] = orig_home
        else:
            os.environ.pop("PEERPEDIA_HOME", None)
        paths_mod.DATA_ROOT = orig_data
        paths_mod.ARTICLES_DIR = orig_articles


def make_user(db, name, public_key=None):
    from peerpedia_core.core.users import create_user
    return create_user(db, name=name, public_key=public_key or ("00" * 32))


def make_signing_key(author_email):
    """Derive deterministic signing key + pubkey from email (matches production).

    Returns (private_key_bytes, pubkey_hex) where private_key_bytes are the
    raw 32-byte Ed25519 seed — ready for ``temp_signing_key()``.
    """
    salt = hashlib.sha256(author_email.encode()).hexdigest()[:32]
    priv_bytes, pub_bytes = derive_key_pair(_TEST_PASSWORD, salt)
    return priv_bytes, pub_bytes.hex()
