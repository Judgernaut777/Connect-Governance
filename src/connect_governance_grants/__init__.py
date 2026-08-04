"""Execution grants — signed, tamper-evident authorization artifacts (R4).

A Decision whose outcome is Allowed may issue an **execution grant**: a
canonical-JSON payload signed with Ed25519, which an enforcing provider (R5:
ToolConnect) later verifies and redeems at the point of effect (ADR-038).

This package is the pure core of that capability, held to the same isolation
discipline as the Decision Kernel (ADR-049):

  * no system clock — validity is evaluated against a caller-supplied instant
  * no randomness — Ed25519 signing is deterministic; identical payload and key
    produce byte-identical signatures
  * no network, no filesystem, no mutable module state
  * key *generation* does not live here at all (see
    ``connect_governance.keys``); only sign and verify do

The one dependency beyond the Kernel's is ``cryptography`` (Ed25519, per
ADR-050). The signature scheme and key custody are OD-007 and OD-008, resolved
by ADR-050 and ADR-051 respectively.

The normative behaviour of this package is pinned by the grant conformance
vectors under ``conformance/grant-vectors/`` — same discipline as the Kernel
vectors: a failing vector means the implementation or the specification is
wrong, never something to be edited into agreement.
"""

from .signing import (
    GRANT_FORMAT_VERSION,
    ExecutionGrant,
    GrantPayload,
    VerificationResult,
    public_key_id,
    sign_grant,
    verify_grant,
)

__all__ = [
    "GRANT_FORMAT_VERSION",
    "ExecutionGrant",
    "GrantPayload",
    "VerificationResult",
    "public_key_id",
    "sign_grant",
    "verify_grant",
]
