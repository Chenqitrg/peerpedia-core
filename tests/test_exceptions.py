# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for semantic exception classes."""

from peerpedia_core.exceptions import (
    AmbiguousError,
    BadRequestError,
    ConflictError,
    MergeConflictError,
    NotAuthorizedError,
    NotFoundError,
    PeerpediaError,
    ProtocolError,
    SignatureVerificationError,
    TransportError,
)


class TestPeerpediaError:
    def test_base_error_stores_detail(self):
        e = PeerpediaError("something went wrong")
        assert e.detail == "something went wrong"

    def test_base_error_stores_detail_string(self):
        e = PeerpediaError("review conflict detected")
        assert e.detail == "review conflict detected"

    def test_subclass_inherits_from_base(self):
        assert issubclass(NotFoundError, PeerpediaError)
        assert issubclass(NotAuthorizedError, PeerpediaError)
        assert issubclass(ConflictError, PeerpediaError)
        assert issubclass(BadRequestError, PeerpediaError)

    def test_subclass_instance_is_peerpedia_error(self):
        for cls in [NotFoundError, NotAuthorizedError, ConflictError, BadRequestError]:
            assert isinstance(cls("test"), PeerpediaError)


class TestSemanticNames:
    """Semantic exceptions must carry no HTTP concepts in their names."""

    def test_no_status_code_attribute(self):
        """None of the semantic exceptions should have a status_code."""
        for cls in [NotFoundError, NotAuthorizedError, ConflictError, BadRequestError]:
            e = cls("test")
            assert not hasattr(e, "status_code"), f"{cls.__name__} should not have status_code"


# ═══════════════════════════════════════════════════════════════════════════════
# Additional exception subclasses
# ═══════════════════════════════════════════════════════════════════════════════


class TestExceptionSubclasses:
    def test_ambiguous_error_stores_candidates(self):
        """AmbiguousError carries the list of matching candidate IDs."""
        e = AmbiguousError("multiple matches", resource_type="article",
                           candidates=["art-1", "art-2"])
        assert e.code == "AMBIGUOUS"
        assert e.resource_type == "article"
        assert e.candidates == ["art-1", "art-2"]

    def test_signature_verification_error_stores_reason(self):
        """SignatureVerificationError carries reason and pubkey context."""
        e = SignatureVerificationError("bad sig", reason="mismatch",
                                       pubkey="abc123")
        assert e.code == "SIGNATURE_ERROR"
        assert e.reason == "mismatch"
        assert e.pubkey == "abc123"

    def test_transport_error_stores_server(self):
        """TransportError carries server URL and optional status_code."""
        e = TransportError("timeout", server="https://peer.example.com",
                           status_code=504)
        assert e.code == "TRANSPORT_ERROR"
        assert e.server == "https://peer.example.com"
        assert e.status_code == 504

    def test_protocol_error_stores_server(self):
        """ProtocolError carries server URL and optional status_code."""
        e = ProtocolError("bad response", server="https://peer.example.com",
                          status_code=500)
        assert e.code == "PROTOCOL_ERROR"
        assert e.server == "https://peer.example.com"
        assert e.status_code == 500

    def test_merge_conflict_inherits_from_conflict(self):
        """MergeConflictError is a ConflictError subtype."""
        assert issubclass(MergeConflictError, ConflictError)
        e = MergeConflictError("merge failed", conflicting_entity="article-1")
        assert e.code == "CONFLICT"

    def test_code_override_via_kwarg(self):
        """Passing code=… as a kwarg overrides the class-level default."""
        e = NotFoundError(code="USER_NOT_FOUND", detail="no such user",
                          resource_type="user", resource_id="uid-1")
        assert e.code == "USER_NOT_FOUND"
        assert e.detail == "no such user"

    def test_detail_defaults_to_code(self):
        """When detail is empty and code != 'ERROR', detail falls back to code."""
        e = NotFoundError()
        assert e.detail == "NOT_FOUND"

    def test_all_subclasses_are_peerpedia_errors(self):
        """Every exception in the hierarchy is an instance of PeerpediaError."""
        for cls in [AmbiguousError, SignatureVerificationError, TransportError,
                     ProtocolError, MergeConflictError]:
            assert issubclass(cls, PeerpediaError)
            assert isinstance(cls("test"), PeerpediaError)
