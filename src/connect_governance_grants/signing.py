"""Grant signing and verification — pure functions over canonical bytes.

The artifact shape:

  * :class:`GrantPayload` — everything the grant binds to (ROADMAP R4, RA v0.2
    §7): the Work Request and revision, the requesting Principal, Organization
    and Workspace, the permitted provider and operations, material argument
    constraints, data classifications, budget limit, validity window,
    delegation limits, Policy and Kernel versions, the issuing key id, and the
    originating Decision Record.
  * :class:`ExecutionGrant` — the payload plus the Ed25519 signature over its
    canonical encoding (:func:`connect_governance_kernel.canonical_json`), so
    "the bytes that were signed" is a checkable, language-neutral claim.

Determinism: Ed25519 is a deterministic signature scheme. The same payload and
the same key produce the same signature, on any machine, at any wall-clock
time — which is what makes grant issuance reproducible and grant vectors
possible at all.

Verification evaluates the validity window against a caller-supplied instant
(``at``), never a clock, using the same half-open semantics as the Kernel's
authority windows: ``not_before <= t < not_after``, with a null bound open on
that side.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any, Literal, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)
from pydantic import BaseModel, ConfigDict, Field

from connect_governance_kernel import canonical_json, parse_rfc3339

#: Wire-format version of the grant artifact. Any change to the payload shape
#: or the signed-bytes rule bumps this version so a verifier can refuse a
#: format it does not understand rather than silently misinterpreting it.
GRANT_FORMAT_VERSION = "1"

SIGNATURE_SCHEME = "Ed25519"


class _Frozen(BaseModel):
    """Immutable and closed to unknown fields — same contract as Kernel types."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class GrantPayload(_Frozen):
    """The bound content of an execution grant. Everything here is signed."""

    grant_format_version: str
    grant_id: str
    #: The Decision Record whose Allowed outcome authorized this grant (R3/R4
    #: linkage; ADR-037 correlation across record kinds).
    decision_record_id: str
    work_request_id: str
    work_request_revision: str | None = None
    requesting_principal_id: str
    organization_id: str
    workspace_id: str
    #: The single provider this grant may be redeemed against.
    provider_id: str
    #: The exact operations this grant permits; anything else is denied.
    permitted_operations: Sequence[str]
    #: Material argument constraints: canonical-JSON-encoded argument bindings
    #: or constraints resolved by the issuer (RA v0.2 §7). Opaque to signing.
    argument_constraints: Mapping[str, Any] = Field(default_factory=dict)
    data_classifications: Sequence[str] = ()
    budget_limit_usd: float | None = None
    delegation_depth: int = 0
    delegation_max_depth: int | None = None
    policy_versions: Sequence[str] = ()
    kernel_version: str
    #: Validity window, RFC 3339. Half-open: [not_before, not_after).
    not_before: str | None = None
    not_after: str | None = None
    #: Revocation state at issuance. Revocation itself is a governed act that
    #: produces a new record; a grant never self-modifies.
    revocation_state: Literal["active"] = "active"
    issued_at: str
    issuer_key_id: str
    correlation_id: str | None = None


class ExecutionGrant(_Frozen):
    """A signed grant: the payload plus the signature over its canonical form.

    Not strict (like the Kernel's Decision): a grant must round-trip from its
    own canonical encoding for verification by parties that only hold JSON.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=False)

    payload: GrantPayload
    signature_scheme: str
    #: Base64url (no padding) of the 64-byte Ed25519 signature.
    signature: str


class VerificationResult(_Frozen):
    """Structured verification outcome — evidence, not a bare boolean."""

    valid: bool
    signature_valid: bool
    within_validity_window: bool
    #: Stable machine-readable failure codes, empty when valid:
    #: "signature_mismatch", "not_yet_valid", "expired", "key_id_mismatch".
    failure_codes: Sequence[str] = ()
    issuer_key_id: str


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def public_key_id(public_key_pem: str) -> str:
    """The stable identifier of a verification key: sha256 of its raw bytes.

    Recorded on every grant so a verifier can tell "signed by an unknown key"
    from "signature invalid", and so key rotation (ADR-051) is auditable.
    """
    key = load_pem_public_key(public_key_pem.encode("utf-8"))
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("issuer keys must be Ed25519")
    raw = key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return "ed25519:" + hashlib.sha256(raw).hexdigest()


def signed_bytes(payload: GrantPayload) -> bytes:
    """The exact bytes the signature covers: the canonical form of the payload.

    Signing the canonical encoding — not a wire transcript — is what lets a
    provider re-serialize a grant it received and still verify it (R5).
    """
    return canonical_json(payload).encode("utf-8")


def sign_grant(payload: GrantPayload, private_key_pem: str) -> ExecutionGrant:
    """Sign a payload with an Ed25519 private key. Deterministic, no I/O.

    ``issued_at`` and the validity window are fields the caller set on the
    payload; this function reads no clock and invents nothing.
    """
    if payload.grant_format_version != GRANT_FORMAT_VERSION:
        raise ValueError(
            f"unsupported grant format {payload.grant_format_version!r}; "
            f"this signer emits {GRANT_FORMAT_VERSION!r}"
        )
    key = load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("issuer keys must be Ed25519")
    actual_id = public_key_id(
        key.public_key()
        .public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        .decode("utf-8")
    )
    if payload.issuer_key_id != actual_id:
        raise ValueError(
            f"payload names issuer {payload.issuer_key_id!r} but the signing "
            f"key is {actual_id!r}; the grant must not misattribute its issuer"
        )
    signature = key.sign(signed_bytes(payload))
    return ExecutionGrant(
        payload=payload,
        signature_scheme=SIGNATURE_SCHEME,
        signature=_b64e(signature),
    )


def verify_grant(
    grant: ExecutionGrant,
    public_key_pem: str,
    *,
    at: str,
    expected_key_id: str | None = None,
) -> VerificationResult:
    """Verify a grant's signature and validity window. Pure.

    ``at`` is the caller's instant — the provider decides what "now" means;
    this function never reads a clock. Window semantics match the Kernel's
    authority windows: half-open, ``not_before <= t < not_after``.

    A structural problem (malformed signature, wrong scheme, wrong key) is
    reported as ``signature_valid=False`` rather than raised: a verifier at
    the point of effect must produce a denial it can explain, not an
    exception it cannot.
    """
    failures: list[str] = []
    key_id = grant.payload.issuer_key_id

    if expected_key_id is not None and key_id != expected_key_id:
        failures.append("key_id_mismatch")

    signature_valid = False
    if grant.signature_scheme == SIGNATURE_SCHEME:
        try:
            key = load_pem_public_key(public_key_pem.encode("utf-8"))
            key.verify(_b64d(grant.signature), signed_bytes(grant.payload))
            signature_valid = True
        except (InvalidSignature, ValueError):
            signature_valid = False
    if not signature_valid:
        failures.append("signature_mismatch")

    within_window = True
    t = parse_rfc3339(at)
    p = grant.payload
    if p.not_before is not None and t < parse_rfc3339(p.not_before):
        within_window = False
        failures.append("not_yet_valid")
    if p.not_after is not None and t >= parse_rfc3339(p.not_after):
        within_window = False
        failures.append("expired")

    valid = signature_valid and within_window and not failures
    return VerificationResult(
        valid=valid,
        signature_valid=signature_valid,
        within_validity_window=within_window,
        failure_codes=tuple(failures),
        issuer_key_id=key_id,
    )


__all__ = [
    "GRANT_FORMAT_VERSION",
    "SIGNATURE_SCHEME",
    "ExecutionGrant",
    "GrantPayload",
    "VerificationResult",
    "public_key_id",
    "sign_grant",
    "signed_bytes",
    "verify_grant",
]
