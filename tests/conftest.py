# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared fixtures for core tests."""

import tempfile

import pytest

from peerpedia_core.storage.db.engine import Base, get_engine, init_db


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
