# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared fixtures for app layer spec tests."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

import peerpedia_core.storage.db.models  # noqa: F401 — register ORM models
from peerpedia_core.app.context import AppContext, write_session
from peerpedia_core.crypto import derive_key_pair, new_salt
from peerpedia_core.storage.db.engine import Base, get_engine, get_session


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
def transport():
    return Mock()


@pytest.fixture
def ctx(db, transport):
    """An AppContext with no logged-in user."""
    return AppContext(db=db, transport=transport)


@pytest.fixture
def articles_dir():
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


def login(ctx, name="Alice") -> AppContext:
    """Create a user directly in storage + return a logged-in AppContext."""
    from peerpedia_core.storage.db.crud_user import create_user
    import hashlib
    from peerpedia_core.crypto import derive_key_pair
    salt = hashlib.sha256(f"{name}@peerpedia".encode()).hexdigest()[:32]
    priv_bytes, pub_bytes = derive_key_pair("test123", salt)
    pubkey_hex = pub_bytes.hex()

    u = create_user(ctx.db, name=name, public_key=pubkey_hex, affiliation="Test")
    ctx.db.commit()
    return AppContext(
        db=ctx.db, transport=ctx.transport,
        current_user_id=u.id,
        signing_key_bytes=priv_bytes,
        pubkey_hex=pubkey_hex,
    )
