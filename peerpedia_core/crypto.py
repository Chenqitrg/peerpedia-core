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
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

# scrypt parameters — ~100ms on modern hardware, memory-hard against brute force
_SCRYPT_N = 2 ** 14  # 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32


def derive_key_pair(password: str, salt_hex: str) -> tuple[bytes, bytes]:
    """Derive an Ed25519 key pair from a password and salt.

    Returns (private_key_bytes, public_key_bytes) — 32 bytes each, raw.
    Deterministic: same password + same salt always produces the same key pair.
    """
    salt = bytes.fromhex(salt_hex)
    seed = hashlib.scrypt(
        password.encode("utf-8"),
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


def pubkey_hex_to_ssh_line(pubkey_hex: str) -> str:
    """Convert a raw Ed25519 public key hex to an SSH allowed_signers line.

    Returns ``"ssh-ed25519 <base64>"`` suitable for writing to an
    allowed_signers file for ``git verify-commit``.

    Raises ValueError if the key is not 32 bytes.
    """
    raw = bytes.fromhex(pubkey_hex)
    if len(raw) != 32:
        raise ValueError(f"Ed25519 public key must be 32 bytes, got {len(raw)}")
    # SSH wire format: string "ssh-ed25519" + string <key>
    wire = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32) + raw
    return "ssh-ed25519 " + base64.b64encode(wire).decode("ascii")


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
    """
    priv_pem = serialize_private_key_pem(private_key_bytes)
    fd, path = tempfile.mkstemp(suffix="_peerpedia_ed25519")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(priv_pem)
        os.chmod(path, 0o600)
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    return Path(path)


def new_salt() -> str:
    """Generate a new random 16-byte salt, hex-encoded."""
    return secrets.token_bytes(16).hex()


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
