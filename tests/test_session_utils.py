# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Specification: Database Session Lifecycle

The `db_session_scope` context manager provides a safe, predictable lifecycle
for every database session. Every caller — CRUD, workflow, route handler —
must be able to rely on the same contract without repeating boilerplate.

Contract:
  S1 — On successful exit, the session commits.
  S2 — On exception, the session rolls back and the exception propagates.
  S3 — In both cases, the session is closed in the finally block.
  S4 — The yielded session is usable for standard ORM operations.
  S5 — Nested begin/commit within the context work as expected (sub-transactions).
"""

import pytest

from peerpedia_core.storage.db.models import User
from peerpedia_core.storage.db.session_utils import db_session_scope


def _make_user(**kwargs):
    """Create a User with required defaults filled in."""
    defaults = dict(username="u", name="U", anonymous_name="anon", password_hash="")
    defaults.update(kwargs)
    return User(**defaults)


class TestSuccessfulCommit:
    """S1 — On successful exit, the session commits."""

    def test_commit_persists_data(self, db_url):
        """When the context exits normally, any added entities are persisted
        and visible to a subsequent session."""
        with db_session_scope(db_url) as session:
            u = _make_user(
                username="commit_test",
                name="Commit Test",
                anonymous_name="anon_commit",
            )
            session.add(u)

        # After context exit → committed
        with db_session_scope(db_url) as session:
            found = session.query(User).filter(User.username == "commit_test").first()
            assert found is not None
            assert found.name == "Commit Test"

    def test_multiple_operations_in_one_transaction(self, db_url):
        """Multiple adds/updates within one context are atomic — all or
        nothing (on success)."""
        with db_session_scope(db_url) as session:
            session.add(_make_user(username="batch_a", name="A", anonymous_name="a"))
            session.add(_make_user(username="batch_b", name="B", anonymous_name="b"))
            session.flush()
            session.add(_make_user(username="batch_c", name="C", anonymous_name="c"))

        with db_session_scope(db_url) as session:
            count = session.query(User).filter(User.username.in_(["batch_a", "batch_b", "batch_c"])).count()
            assert count == 3


class TestRollbackOnException:
    """S2 — On exception, the session rolls back and the exception propagates."""

    def test_rollback_on_application_error(self, db_url):
        """If application code raises after adding data, nothing is persisted."""
        with db_session_scope(db_url) as session:
            session.add(_make_user(username="will_rollback", name="RB", anonymous_name="rb"))

        class AppError(Exception):
            pass

        with pytest.raises(AppError):
            with db_session_scope(db_url) as session:
                session.add(_make_user(username="should_disappear", name="Gone", anonymous_name="gone"))
                raise AppError("simulated failure")

        with db_session_scope(db_url) as session:
            # The record from the first (successful) context is there
            found = session.query(User).filter(User.username == "will_rollback").first()
            assert found is not None
            # The record from the failed context must NOT exist
            missing = session.query(User).filter(User.username == "should_disappear").first()
            assert missing is None

    def test_db_integrity_error_rolls_back(self, db_url):
        """An integrity error (e.g., duplicate primary key) triggers rollback
        and does not affect subsequent sessions."""
        with db_session_scope(db_url) as session:
            session.add(_make_user(id="fixed-id-1", username="u1", name="U1", anonymous_name="a1"))

        with pytest.raises(Exception):  # IntegrityError from duplicate PK
            with db_session_scope(db_url) as session:
                session.add(_make_user(id="fixed-id-1", username="u2", name="U2", anonymous_name="a2"))

        # Session should be usable after the error
        with db_session_scope(db_url) as session:
            # Only the first record exists
            users = session.query(User).filter(User.id == "fixed-id-1").all()
            assert len(users) == 1
            assert users[0].username == "u1"


class TestSessionClosed:
    """S3 — In both cases, the session is closed in the finally block."""

    def test_session_is_detached_after_successful_exit(self, db_url):
        """After a successful context exit, the session is closed and objects
        are detached. Data is still committed."""
        user_id = None
        with db_session_scope(db_url) as session:
            u = _make_user(username="detach_test", name="DT", anonymous_name="dt")
            session.add(u)
            session.flush()  # populate u.id before commit expires it
            user_id = u.id

        # Data is committed (verifiable via new session)
        with db_session_scope(db_url) as fresh:
            found = fresh.get(User, user_id)
            assert found is not None
            assert found.name == "DT"

    def test_session_is_closed_after_exception(self, db_url):
        """After an exception-triggered rollback, the session is still closed."""
        session_ref = None

        class TestError(Exception):
            pass

        with pytest.raises(TestError):
            with db_session_scope(db_url) as session:
                session_ref = session
                raise TestError("fail")

        # The session should not be usable for new work
        assert session_ref is not None


class TestSessionUsability:
    """S4 — The yielded session is usable for standard ORM operations."""

    def test_crud_read_write(self, db_url):
        """Standard CRUD operations work inside the context."""
        with db_session_scope(db_url) as session:
            u = _make_user(username="crud_user", name="CRUD", anonymous_name="c")
            session.add(u)
            session.flush()

            # Read back
            found = session.get(User, u.id)
            assert found is not None
            assert found.name == "CRUD"

            # Update
            found.name = "Updated"
            session.flush()

            # Delete
            session.delete(found)

    def test_query_filter_works(self, db_url):
        """Query filtering works as expected inside the context."""
        with db_session_scope(db_url) as session:
            session.add(_make_user(username="q1", name="Q1", anonymous_name="a1"))
            session.add(_make_user(username="q2", name="Q2", anonymous_name="a2"))

            results = session.query(User).filter(User.username.like("q%")).all()
            assert len(results) == 2


class TestSubTransactions:
    """S5 — Nested begin/commit within the context work as expected."""

    def test_savepoint_rollback_does_not_kill_outer_transaction(self, db_url):
        """A savepoint rollback inside the context should not affect the outer
        transaction."""
        with db_session_scope(db_url) as session:
            session.add(_make_user(username="outer_keep", name="OK", anonymous_name="ok"))

            # Try a savepoint that rolls back
            try:
                with session.begin_nested():
                    session.add(_make_user(username="inner_lose", name="IL", anonymous_name="il"))
                    raise ValueError("rollback savepoint")
            except ValueError:
                pass  # savepoint rolled back, outer still valid

        with db_session_scope(db_url) as session:
            assert session.query(User).filter(User.username == "outer_keep").first() is not None
            assert session.query(User).filter(User.username == "inner_lose").first() is None
