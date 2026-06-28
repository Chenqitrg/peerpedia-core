# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Semantic exceptions — no HTTP concepts, pure business logic.

Each exception carries a machine-readable ``code`` so AI agents and CLI
handlers can route errors without parsing natural-language detail strings.
Context fields (``resource_type``, ``resource_id``, …) are optional but
should be supplied whenever the information is available at the raise site.

Exception hierarchy
-------------------
PeerpediaError (base)       ``code: str``  ``detail: str``  ``context: dict``
  ├── NotFoundError          resource_type, resource_id
  ├── NotAuthorizedError     permission, resource_type, resource_id
  ├── ConflictError          conflicting_entity
  ├── MergeConflictError     merge-specific conflict (can't auto-resolve)
  ├── AmbiguousError         exact ID match returned multiple records
  ├── BadRequestError        field, bad_value
  ├── SignatureVerificationError  reason, pubkey
  ├── TransportError         server, status_code
  └── ProtocolError          server, status_code

Usage pattern
-------------
All policy functions (``policies/articles.py``) and orchestration functions
(``commands/``) raise these.  The CLI catches them in command handlers and
calls ``_die(msg)`` to print the error and exit.  The REPL catches them in
``_dispatch`` and prints without exiting.

Backward compatibility
----------------------
All existing ``raise FooError("message")`` sites continue to work.
All existing ``e.detail`` accesses continue to work.
The new ``code``, ``context``, and named fields are additive.
"""


class PeerpediaError(Exception):
    """Base for all PeerPedia business-logic errors.

    Attributes:
        detail: Human-readable description (always present).
        code:  Machine-readable error code (default ``"ERROR"``).
        context:  Arbitrary key-value pairs for structured error output.
    """

    code: str = "ERROR"

    def __init__(self, detail: str = "", **context):
        # Allow callers to pass ``code=`` — it becomes an instance attribute
        # overriding the class-level code (e.g. "NOT_FOUND" → "USER_NOT_FOUND").
        if "code" in context:
            self.code = context.pop("code")
        if not detail and self.code != "ERROR":
            detail = self.code
        super().__init__(detail)
        self.detail = detail
        self.context = context
        for k, v in context.items():
            setattr(self, k, v)


class NotFoundError(PeerpediaError):
    """Requested resource does not exist.

    Optional context keys:
        resource_type:  e.g. ``"article"``, ``"user"``, ``"repo"``
        resource_id:    The identifier that was looked up.
    """

    code = "NOT_FOUND"

    def __init__(self, detail: str = "", resource_type: str = "", resource_id: str = "", **kwargs):
        super().__init__(detail, resource_type=resource_type, resource_id=resource_id, **kwargs)


class NotAuthorizedError(PeerpediaError):
    """User lacks permission for the requested action.

    Optional context keys:
        permission:      What permission was required (e.g. ``"maintainer"``).
        resource_type:   e.g. ``"article"``
        resource_id:     The resource the user tried to act on.
    """

    code = "NOT_AUTHORIZED"

    def __init__(self, detail: str = "", permission: str = "",
                 resource_type: str = "", resource_id: str = "", **kwargs):
        super().__init__(detail, permission=permission,
                         resource_type=resource_type, resource_id=resource_id, **kwargs)


class ConflictError(PeerpediaError):
    """Request conflicts with the current state of the resource.

    Optional context keys:
        conflicting_entity:  What already exists or is in the way.
    """

    code = "CONFLICT"

    def __init__(self, detail: str = "", conflicting_entity: str = "", **kwargs):
        super().__init__(detail, conflicting_entity=conflicting_entity, **kwargs)


class MergeConflictError(ConflictError):
    """Raised when a git merge encounters conflicts that can't auto-resolve.

    Canonical definition — imported by both ``storage/git_backend`` and
    ``bundle/git_bundle`` so callers can catch a single type regardless of
    which layer raises it.
    """

    def __init__(self, detail: str = "", conflicting_entity: str = "", **kwargs):
        super().__init__(detail, conflicting_entity=conflicting_entity, **kwargs)


class AmbiguousError(PeerpediaError):
    """Exact ID lookup returned multiple records — data integrity violation.

    This is NOT for fuzzy-search ambiguity (which is normal).  It signals
    that the database contains duplicate records for what should be a unique
    identifier, or that a UUID prefix matches too many records.

    Optional context keys:
        resource_type:  e.g. ``"article"``, ``"user"``
        candidates:     List of matching IDs (truncated).
    """

    code = "AMBIGUOUS"

    def __init__(self, detail: str = "", resource_type: str = "",
                 candidates: list[str] | None = None, **kwargs):
        super().__init__(detail, resource_type=resource_type,
                         candidates=candidates or [], **kwargs)


class BadRequestError(PeerpediaError):
    """Input is invalid or missing required data.

    Optional context keys:
        field:      Which field was invalid.
        bad_value:  The value that was rejected (truncated).
    """

    code = "BAD_REQUEST"

    def __init__(self, detail: str = "", field: str = "", bad_value: str = "", **kwargs):
        super().__init__(detail, field=field, bad_value=bad_value, **kwargs)


class SignatureVerificationError(PeerpediaError):
    """Commit signature is invalid, missing, or key mismatch (TOFU).

    Optional context keys:
        reason:  Why verification failed (``"missing"``, ``"mismatch"``, ``"tofu"``).
        pubkey:  The public key involved (truncated if needed).
    """

    code = "SIGNATURE_ERROR"

    def __init__(self, detail: str = "", reason: str = "", pubkey: str = "", **kwargs):
        super().__init__(detail, reason=reason, pubkey=pubkey, **kwargs)


class TransportError(PeerpediaError):
    """Network-level error: unreachable, timeout, DNS, connection refused.

    Optional context keys:
        server:       The peer server URL.
        status_code:  HTTP status code if available.
    """

    code = "TRANSPORT_ERROR"

    def __init__(self, detail: str = "", server: str = "", status_code: int | None = None, **kwargs):
        super().__init__(detail, server=server, status_code=status_code, **kwargs)


class ProtocolError(PeerpediaError):
    """Protocol-level error: unexpected HTTP status, malformed response body.

    Optional context keys:
        server:       The peer server URL.
        status_code:  HTTP status code if available.
    """

    code = "PROTOCOL_ERROR"

    def __init__(self, detail: str = "", server: str = "", status_code: int | None = None, **kwargs):
        super().__init__(detail, server=server, status_code=status_code, **kwargs)
