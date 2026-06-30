# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Cryptographic utilities — key derivation, signing, verification."""

import pytest

from peerpedia_core.crypto import (
    derive_key_pair,
    derive_pubkey_hex,
    new_salt,
    pubkey_hex_to_ssh_line,
    sha256_hex,
    sign_detached,
    validate_pubkey_hex,
    validate_sig_hex,
    verify_body_hash,
    verify_signature,
)
from peerpedia_core.exceptions import BadRequestError


class TestKeyDerivation:
    def test_same_password_same_salt_yields_same_key(self):
        k1 = derive_key_pair("hunter2", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        k2 = derive_key_pair("hunter2", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        assert k1 == k2

    def test_different_password_yields_different_key(self):
        k1 = derive_key_pair("hunter2", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        k2 = derive_key_pair("hunter3", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        assert k1 != k2

    def test_different_salt_yields_different_key(self):
        k1 = derive_key_pair("hunter2", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        k2 = derive_key_pair("hunter2", "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        assert k1 != k2

    def test_derive_pubkey_hex_deterministic(self):
        pk1 = derive_pubkey_hex("hunter2", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        pk2 = derive_pubkey_hex("hunter2", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        assert pk1 == pk2

    def test_new_salt_is_hex(self):
        salt = new_salt()
        assert len(salt) == 32  # 16 bytes → 32 hex chars
        int(salt, 16)  # valid hex


class TestSigningAndVerification:
    def test_sign_and_verify_roundtrip(self):
        priv, pub = derive_key_pair("hunter2", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        message = b"hello world"
        sig = sign_detached(priv, message)
        assert verify_signature(pub, message, sig) is True

    def test_wrong_message_fails_verification(self):
        priv, pub = derive_key_pair("hunter2", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        sig = sign_detached(priv, b"hello world")
        assert verify_signature(pub, b"wrong message", sig) is False

    def test_wrong_key_fails_verification(self):
        priv, _ = derive_key_pair("hunter2", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        _, pub2 = derive_key_pair("hunter3", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        sig = sign_detached(priv, b"hello world")
        assert verify_signature(pub2, b"hello world", sig) is False


class TestPubkeyValidation:
    def test_valid_pubkey_hex(self):
        pk = "fe40" * 16  # 64 hex chars
        raw = validate_pubkey_hex(pk)
        assert len(raw) == 32

    def test_invalid_pubkey_length_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_PUBKEY_LEN"):
            validate_pubkey_hex("fe40" * 4)  # 16 chars, not 64

    def test_invalid_pubkey_hex_raises(self):
        with pytest.raises(ValueError):
            validate_pubkey_hex("gg" * 32)  # invalid hex → ValueError from bytes.fromhex

    def test_valid_sig_hex(self):
        sig = "ab" * 64  # 128 hex chars
        raw = validate_sig_hex(sig)
        assert len(raw) == 64

    def test_invalid_sig_length_raises(self):
        with pytest.raises(BadRequestError, match="INVALID_SIG_LEN"):
            validate_sig_hex("ab" * 4)


class TestHashFunctions:
    def test_sha256_hex(self):
        result = sha256_hex(b"hello")
        assert len(result) == 64  # SHA-256 → 32 bytes → 64 hex chars

    def test_sha256_hex_empty(self):
        assert sha256_hex(b"") == ""

    def test_verify_body_hash_pass(self):
        verify_body_hash(b"hello", sha256_hex(b"hello"))

    def test_verify_body_hash_mismatch(self):
        with pytest.raises(BadRequestError, match="BODY_HASH_MISMATCH"):
            verify_body_hash(b"hello", sha256_hex(b"world"))


class TestSshFormat:
    def test_pubkey_hex_to_ssh_line(self):
        pk = derive_pubkey_hex("hunter2", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4")
        line = pubkey_hex_to_ssh_line(pk)
        assert line.startswith("ssh-ed25519 ")
        assert len(line) > len("ssh-ed25519 ")

    def test_invalid_pubkey_raises(self):
        with pytest.raises(BadRequestError):
            pubkey_hex_to_ssh_line("bad")
