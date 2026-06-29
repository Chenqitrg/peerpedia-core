# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Cryptographic utilities — Ed25519 key derivation, signing, verification.

Key derivation (registration / login):
  password ──scrypt──→ 32-byte seed ──Ed25519──→ (private_key, public_key)
  Same password + same salt = same key pair (deterministic).

Commit signing uses git's native ``gpg.format=ssh`` with Ed25519 keys.
Verification uses the pubkey embedded in each commit message (TOFU model).
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import struct
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from peerpedia_core.exceptions import BadRequestError

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

# scrypt parameters — ~100ms on modern hardware, memory-hard against brute force
_SCRYPT_N = 2 ** 14  # 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32

# Ed25519 constants
_SSH_ALGO = "ssh-ed25519"
_SSH_ALGO_BYTES = b"ssh-ed25519"
_SSH_ALGO_LEN = 11
_PUBKEY_HEX_LEN = 64
_PUBKEY_BYTES = 32
_SIG_HEX_LEN = 128

# File I/O
_KEYFILE_SUFFIX = "_peerpedia_ed25519"
_SIGNERS_SUFFIX = "_allowed_signers"
_KEYFILE_PERMS = 0o600
_SALT_BYTES = 16

# Wire format
_STRUCT_FMT = ">I"


def derive_key_pair(password: str, salt_hex: str) -> tuple[bytes, bytes]:
    """Derive an Ed25519 key pair from a password and salt.

    Returns (private_key_bytes, public_key_bytes) — 32 bytes each, raw.
    Deterministic: same password + same salt always produces the same key pair.
    """
    salt = bytes.fromhex(salt_hex)
    seed = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
    public_key = private_key.public_key()
    return (
        _private_key_to_bytes(private_key),
        _public_key_to_bytes(public_key),
    )


def derive_pubkey_hex(password: str, salt_hex: str) -> str:
    """Derive only the public key hex (for registration — no private key needed)."""
    _, pubkey = derive_key_pair(password, salt_hex)
    return pubkey.hex()


def validate_pubkey_hex(pubkey_hex: str) -> bytes:
    """Return raw 32-byte public key, or raise BadRequestError."""
    if len(pubkey_hex) != _PUBKEY_HEX_LEN:
        raise BadRequestError(code="INVALID_PUBKEY_LEN", length=len(pubkey_hex))
    raw = bytes.fromhex(pubkey_hex)
    if len(raw) != _PUBKEY_BYTES:
        raise BadRequestError(code="INVALID_PUBKEY_BYTES", length=len(raw))
    return raw


def validate_sig_hex(sig_hex: str) -> bytes:
    """Return raw 64-byte signature, or raise BadRequestError."""
    if len(sig_hex) != _SIG_HEX_LEN:
        raise BadRequestError(code="INVALID_SIG_LEN", length=len(sig_hex))
    return bytes.fromhex(sig_hex)


def sha256_hex(data: bytes) -> str:
    """SHA-256 hash of *data*, hex-encoded.  Empty bytes → empty string."""
    if not data:
        return ""
    return hashlib.sha256(data).hexdigest()


def verify_body_hash(body: bytes, claimed_hash: str) -> None:
    """Raise BadRequestError if SHA-256 of *body* doesn't match *claimed_hash*."""
    actual = sha256_hex(body)
    if claimed_hash != actual:
        raise BadRequestError(code="BODY_HASH_MISMATCH")


def pubkey_hex_to_ssh_line(pubkey_hex: str) -> str:
    """Convert a raw Ed25519 public key hex to an SSH allowed_signers line.

    Returns ``"ssh-ed25519 <base64>"`` suitable for writing to an
    allowed_signers file for ``git verify-commit``.

    Raises ValueError if the key is not valid.
    """
    raw = validate_pubkey_hex(pubkey_hex)
    wire = (
        struct.pack(_STRUCT_FMT, _SSH_ALGO_LEN) + _SSH_ALGO_BYTES
        + struct.pack(_STRUCT_FMT, _PUBKEY_BYTES) + raw
    )
    return _SSH_ALGO + " " + base64.b64encode(wire).decode()


def _private_key_to_bytes(key: ed25519.Ed25519PrivateKey) -> bytes:
    """Serialize private key to raw 32 bytes."""
    return key.private_bytes_raw()


def _public_key_to_bytes(key: ed25519.Ed25519PublicKey) -> bytes:
    """Serialize public key to raw 32 bytes."""
    return key.public_bytes_raw()


def load_private_key(key_bytes: bytes) -> ed25519.Ed25519PrivateKey:
    """Deserialize raw 32 bytes to Ed25519PrivateKey."""
    return ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes)


def load_public_key(key_bytes: bytes) -> ed25519.Ed25519PublicKey:
    """Deserialize raw 32 bytes to Ed25519PublicKey."""
    return ed25519.Ed25519PublicKey.from_public_bytes(key_bytes)


def serialize_private_key_pem(private_key_bytes: bytes) -> bytes:
    """Serialize raw Ed25519 key bytes to OpenSSH PEM format.

    Returns PEM-encoded bytes suitable for ``ssh-keygen`` signing.
    Pure crypto — no file I/O.
    """
    priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    return priv_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )


def write_key_to_tempfile(private_key_bytes: bytes) -> Path:
    """Write an Ed25519 private key to a chmod 600 temp file.

    Serializes raw key bytes to OpenSSH format so ``ssh-keygen`` can use
    the file for git commit signing.  Callers MUST unlink the returned
    path after use.

    Prefer ``temp_signing_key`` — the context manager that handles cleanup.
    """
    priv_pem = serialize_private_key_pem(private_key_bytes)
    fd, path = tempfile.mkstemp(suffix=_KEYFILE_SUFFIX)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(priv_pem)
        os.chmod(path, _KEYFILE_PERMS)
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    return Path(path)


@contextmanager
def temp_signing_key(private_key_bytes: bytes) -> Generator[Path, None, None]:
    """Context manager that writes a temp key file and cleans it up on exit.

    Usage::

        with temp_signing_key(signing_key_bytes) as key_path:
            commit_hash = commit_article(rp, ..., signing_key=key_path, ...)

    Replaces the repeated ``write_key_to_tempfile / try / finally / unlink``
    pattern that appears in 4 places.
    """
    key_path = write_key_to_tempfile(private_key_bytes)
    try:
        yield key_path
    finally:
        key_path.unlink(missing_ok=True)


def write_allowed_signers_file(email: str, pubkey_ssh_line: str) -> Path:
    """Write a temporary allowed_signers file and return its path.

    *pubkey_ssh_line* is a full SSH public key line
    (``"ssh-ed25519 AAAAC3NzaC1..."``).
    """
    fd, path = tempfile.mkstemp(suffix=_SIGNERS_SUFFIX)
    with os.fdopen(fd, "w") as f:
        f.write(f"{email} {pubkey_ssh_line}\n")
    return Path(path)


def new_salt() -> str:
    """Generate a new random 16-byte salt, hex-encoded."""
    return secrets.token_bytes(_SALT_BYTES).hex()


def sign_detached(private_key_bytes: bytes, message: bytes) -> bytes:
    """Sign a message with the private key. Returns the signature (64 bytes)."""
    key = load_private_key(private_key_bytes)
    return key.sign(message)


def verify_signature(pubkey_bytes: bytes, message: bytes, signature: bytes) -> bool:
    """Verify a detached Ed25519 signature. Returns True if valid."""
    try:
        key = load_public_key(pubkey_bytes)
        key.verify(signature, message)
        return True
    except InvalidSignature:
        return False
