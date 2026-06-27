# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for account CLI handlers and multi-device bootstrap flow."""

import json
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from peerpedia_core.cli.handlers.account import _validate_bootstrap_json
from peerpedia_core.core import create_user_stub, get_user, get_user_by_name
from peerpedia_core.crypto import derive_key_pair, new_salt
from peerpedia_core.storage.db.crud_user import create_user_stub as _crud_create_user_stub
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import User


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def db(engine):
    session = get_session(engine)
    yield session
    session.rollback()
    session.close()


def _make_user_id() -> str:
    return str(uuid.uuid4())


def _make_pubkey() -> str:
    """64 hex chars (32 bytes) — valid Ed25519 public key format."""
    return "fe40" * 16


def _make_salt() -> str:
    """32 hex chars (16 bytes) — valid scrypt salt format."""
    return "8a3c" * 8


# ── create_user_stub (CRUD level) ────────────────────────────────────────


class TestCreateUserStub:
    def test_creates_user_with_correct_fields(self, db):
        """create_user_stub stores id, name, public_key, salt correctly."""
        uid = _make_user_id()
        pubkey = _make_pubkey()
        salt = _make_salt()

        u = _crud_create_user_stub(db, user_id=uid, name="bob",
                                    public_key=pubkey, salt=salt)

        assert u.id == uid
        assert u.name == "bob"
        assert u.public_key == pubkey
        assert u.salt == salt

    def test_duplicate_user_id_raises_integrity_error(self, db):
        """create_user_stub with duplicate user_id raises IntegrityError."""
        uid = _make_user_id()
        _crud_create_user_stub(db, user_id=uid, name="bob",
                                public_key=_make_pubkey(), salt=_make_salt())
        db.flush()

        with pytest.raises(IntegrityError):
            _crud_create_user_stub(db, user_id=uid, name="alice",
                                    public_key=_make_pubkey(), salt=_make_salt())
            db.flush()


# ── Commands facade ──────────────────────────────────────────────────────


class TestCreateUserStubFacade:
    def test_facade_delegates_to_crud(self, db):
        """create_user_stub via commands facade creates correct User."""
        uid = _make_user_id()
        pubkey = _make_pubkey()
        salt = _make_salt()

        u = create_user_stub(db, user_id=uid, name="bob",
                             public_key=pubkey, salt=salt)

        assert u.id == uid
        assert u.public_key == pubkey
        assert u.salt == salt

    def test_facade_stub_retrievable(self, db):
        """User created via facade is retrievable by get_user."""
        uid = _make_user_id()
        create_user_stub(db, user_id=uid, name="carol",
                         public_key=_make_pubkey(), salt=_make_salt())
        db.flush()

        u = get_user(db, uid)
        assert u is not None
        assert u.name == "carol"


# ── _validate_bootstrap_json ─────────────────────────────────────────────


class TestValidateBootstrapJson:
    def test_valid_json_passes(self):
        """Valid bootstrap JSON passes validation without error."""
        data = {
            "user_id": _make_user_id(),
            "name": "bob",
            "public_key": _make_pubkey(),
            "salt": _make_salt(),
        }
        _validate_bootstrap_json(data)  # should not raise

    def test_missing_name_dies(self):
        """Missing 'name' field raises SystemExit."""
        data = {"user_id": _make_user_id(), "public_key": _make_pubkey(), "salt": _make_salt()}
        with pytest.raises(SystemExit):
            _validate_bootstrap_json(data)

    def test_missing_user_id_dies(self):
        """Missing 'user_id' field raises SystemExit."""
        data = {"name": "bob", "public_key": _make_pubkey(), "salt": _make_salt()}
        with pytest.raises(SystemExit):
            _validate_bootstrap_json(data)

    def test_invalid_uuid_dies(self):
        """Non-UUID user_id raises SystemExit."""
        data = {"user_id": "not-a-uuid", "name": "bob",
                "public_key": _make_pubkey(), "salt": _make_salt()}
        with pytest.raises(SystemExit):
            _validate_bootstrap_json(data)

    def test_invalid_pubkey_hex_length_dies(self):
        """public_key with wrong hex length raises SystemExit."""
        data = {"user_id": _make_user_id(), "name": "bob",
                "public_key": "abcd", "salt": _make_salt()}
        with pytest.raises(SystemExit):
            _validate_bootstrap_json(data)

    def test_invalid_pubkey_non_hex_dies(self):
        """public_key with non-hex characters raises SystemExit."""
        data = {"user_id": _make_user_id(), "name": "bob",
                "public_key": "z" * 64, "salt": _make_salt()}
        with pytest.raises(SystemExit):
            _validate_bootstrap_json(data)

    def test_invalid_salt_length_dies(self):
        """salt with wrong hex length raises SystemExit."""
        data = {"user_id": _make_user_id(), "name": "bob",
                "public_key": _make_pubkey(), "salt": "ab"}
        with pytest.raises(SystemExit):
            _validate_bootstrap_json(data)

    def test_invalid_salt_non_hex_dies(self):
        """salt with non-hex characters raises SystemExit."""
        data = {"user_id": _make_user_id(), "name": "bob",
                "public_key": _make_pubkey(), "salt": "g" * 32}
        with pytest.raises(SystemExit):
            _validate_bootstrap_json(data)


# ── Key derivation roundtrip (bootstrap + recover flow) ──────────────────


class TestKeyDerivationRoundtrip:
    def test_stub_then_derive_key_matches(self, db):
        """Bootstrap creates stub → derive_key_pair with correct password
        produces the matching public_key."""
        uid = _make_user_id()
        salt_hex = new_salt()
        password = "test-password-123"

        privkey, pubkey = derive_key_pair(password, salt_hex)
        pubkey_hex = pubkey.hex()

        # Bootstrap: create stub with known salt and pubkey
        _crud_create_user_stub(db, user_id=uid, name="bob",
                                public_key=pubkey_hex, salt=salt_hex)
        db.flush()

        # Recover: look up user, re-derive key
        u = get_user(db, uid)
        assert u is not None
        assert u.salt == salt_hex

        privkey2, pubkey2 = derive_key_pair(password, u.salt)
        assert pubkey2.hex() == pubkey_hex
        assert pubkey2.hex() == u.public_key

    def test_wrong_password_produces_wrong_key(self, db):
        """Deriving with wrong password produces a different public key."""
        uid = _make_user_id()
        salt_hex = new_salt()

        _, pubkey = derive_key_pair("correct-password", salt_hex)

        _crud_create_user_stub(db, user_id=uid, name="bob",
                                public_key=pubkey.hex(), salt=salt_hex)
        db.flush()

        u = get_user(db, uid)
        _, wrong_pubkey = derive_key_pair("wrong-password", u.salt)
        assert wrong_pubkey.hex() != u.public_key


# ── get_user vs get_user_by_name ─────────────────────────────────────────


class TestUserLookupAfterBootstrap:
    def test_get_user_finds_bootstrapped_user(self, db):
        """get_user by ID finds a bootstrapped user."""
        uid = _make_user_id()
        _crud_create_user_stub(db, user_id=uid, name="dave",
                                public_key=_make_pubkey(), salt=_make_salt())
        db.flush()

        u = get_user(db, uid)
        assert u is not None
        assert u.name == "dave"

    def test_get_user_by_name_finds_bootstrapped_user(self, db):
        """get_user_by_name finds a bootstrapped user by name."""
        _crud_create_user_stub(db, user_id=_make_user_id(), name="eve",
                                public_key=_make_pubkey(), salt=_make_salt())
        db.flush()

        users = get_user_by_name(db, "eve")
        assert len(users) == 1
        assert users[0].name == "eve"
