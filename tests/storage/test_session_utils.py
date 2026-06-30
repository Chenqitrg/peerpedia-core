# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for storage/db/session_utils.py — db_session_scope context manager."""

import pytest

from peerpedia_core.storage.db.models import UserStorage


# ── Helper ───────────────────────────────────────────────────────────────────


def _count_users(db_url: str) -> int:
    """Open a fresh session on *db_url* and count users."""
    from peerpedia_core.storage.db.engine import get_engine, get_session

    eng = get_engine(db_url)
    session = get_session(eng)
    count = session.query(UserStorage).count()
    session.close()
    return count


# ═══════════════════════════════════════════════════════════════════════════════
# db_session_scope
# ═══════════════════════════════════════════════════════════════════════════════


class TestDbSessionScope:
    def test_commits_on_success(self, tmp_path):
        """Data written inside the with-block persists after exit —
        callers don't need to manage commit/rollback themselves."""
        from peerpedia_core.storage.db.session_utils import db_session_scope

        db_url = f"sqlite:///{tmp_path}/test_commit.db"
        with db_session_scope(db_url) as session:
            session.add(UserStorage(id="u1", name="test"))
            # No explicit commit — the context manager does it

        count = _count_users(db_url)
        assert count == 1

    def test_rollbacks_on_exception(self, tmp_path):
        """Exception inside the with-block triggers rollback —
        partial data from a failed operation is never persisted."""
        from peerpedia_core.storage.db.session_utils import db_session_scope

        db_url = f"sqlite:///{tmp_path}/test_rollback.db"

        class TestError(Exception):
            pass

        with pytest.raises(TestError):
            with db_session_scope(db_url) as session:
                session.add(UserStorage(id="u1", name="test"))
                raise TestError("simulated failure")

        count = _count_users(db_url)
        assert count == 0

    def test_closes_after_success(self, tmp_path):
        """Session is closed after the with-block exits normally —
        prevents connection leaks in long-running processes."""
        from peerpedia_core.storage.db.session_utils import db_session_scope

        db_url = f"sqlite:///{tmp_path}/test_close.db"
        with db_session_scope(db_url) as session:
            pass

        # After scope exit, session should be closed
        with pytest.raises(Exception):
            session.execute("SELECT 1")

    def test_closes_after_exception(self, tmp_path):
        """Session is closed even when an exception occurs —
        ensures cleanup regardless of error path."""
        from peerpedia_core.storage.db.session_utils import db_session_scope

        db_url = f"sqlite:///{tmp_path}/test_close_exc.db"

        with pytest.raises(ValueError):
            with db_session_scope(db_url) as session:
                raise ValueError("boom")

        # Session must be closed even after exception
        with pytest.raises(Exception):
            session.execute("SELECT 1")

    def test_initializes_db_once(self, tmp_path):
        """Second scope to the same URL does not re-init the DB —
        _db_initialized set prevents redundant create_all calls."""
        from peerpedia_core.storage.db.session_utils import db_session_scope

        db_url = f"sqlite:///{tmp_path}/test_init_once.db"
        # First scope initializes and commits
        with db_session_scope(db_url) as session:
            session.add(UserStorage(id="u1", name="test"))

        # Second scope to same URL reuses the engine, no re-init
        with db_session_scope(db_url) as session:
            # Data from first scope should still be there
            count = session.query(UserStorage).count()
            assert count == 1

    def test_different_urls_independent(self, tmp_path):
        """Different DB URLs get independent initialization —
        data in one DB does not leak to another."""
        from peerpedia_core.storage.db.session_utils import db_session_scope

        db_url_a = f"sqlite:///{tmp_path}/test_a.db"
        db_url_b = f"sqlite:///{tmp_path}/test_b.db"

        with db_session_scope(db_url_a) as session:
            session.add(UserStorage(id="ua", name="test"))
        with db_session_scope(db_url_b) as session:
            session.add(UserStorage(id="ub", name="test"))

        assert _count_users(db_url_a) == 1
        assert _count_users(db_url_b) == 1
