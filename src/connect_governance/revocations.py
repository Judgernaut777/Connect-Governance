"""ADR-052 revocation lists — issuer-signed, monotonic, distributed as files.

The list format is fixed by ADR-052 and R7 builds its issuance half: the
governance plane builds a revocation list, signs it with the same Ed25519
discipline as execution grants (ADR-050), and records it immutably. The
artifact is a *file*: it is distributed alongside the trust root, not polled
at redemption time, so the offline-enforcement property of the provider is
preserved.

Lists are monotonic: ``supersedes`` chains each list to the issuer's previous
list, and the store refuses a list that does not extend the issuer's current
head. Verification (:func:`verify_revocation_list`) is pure and offline —
signature and key id against a caller-supplied trust root, never a clock, no
I/O. Stale-or-missing semantics at redemption are deliberately **not** judged
here: ADR-052 reserves them to the redeemer, which alone knows the grant
windows it is enforcing.

Determinism note: Ed25519 is deterministic and the signed bytes are the
canonical encoding, so identical inputs reproduce an identical list on any
machine — which is what makes revocation-list conformance vectors possible.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any, Mapping, Sequence

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
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from connect_governance_kernel import canonical_json

from .db.models import RevocationListRecord

#: Wire-format version of the revocation-list artifact (ADR-052). Any change
#: to the shape or the signed-bytes rule bumps this so a verifier refuses a
#: format it does not understand.
REVOCATION_LIST_FORMAT_VERSION = "1"

SIGNATURE_SCHEME = "Ed25519"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class RevocationList(_Frozen):
    """A signed revocation list, in the exact ADR-052 wire shape.

    The signature covers the canonical encoding of every field except
    ``signature`` itself. Not strict on values (like the Kernel's Decision):
    a list must round-trip from its own canonical encoding for verification
    by parties that only hold JSON.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=False)

    revocation_list_format_version: str
    issuer_key_id: str
    #: RFC 3339, caller-supplied at issuance — never read from a clock.
    issued_at: str
    revoked_grant_ids: Sequence[str]
    #: The ``list_id`` of the issuer's previous list, or null for the first.
    supersedes: str | None
    list_id: str
    signature_scheme: str
    #: Base64url (no padding) of the 64-byte Ed25519 signature.
    signature: str


class RevocationListVerification(_Frozen):
    """Structured verification outcome — evidence, not a bare boolean.

    Stable machine-readable failure codes, empty when valid:
    ``unsupported_format_version``, ``unsupported_scheme``,
    ``key_id_mismatch``, ``signature_mismatch``. Staleness is not a code
    here — judging a list stale-or-missing requires the redeemer's instant
    and the grant window, both reserved to the redeemer (ADR-052).
    """

    valid: bool
    signature_valid: bool
    failure_codes: Sequence[str] = ()
    issuer_key_id: str
    list_id: str


class RevocationChainRefused(Exception):
    """A list that does not extend the issuer's monotonic chain was refused."""


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _payload_dict(revocation_list: RevocationList | Mapping[str, Any]) -> dict:
    dump = (
        revocation_list.model_dump()
        if isinstance(revocation_list, RevocationList)
        else dict(revocation_list)
    )
    return {k: v for k, v in dump.items() if k != "signature"}


def signed_bytes(revocation_list: RevocationList | Mapping[str, Any]) -> bytes:
    """The exact bytes the signature covers: canonical form, minus ``signature``."""
    return canonical_json(_payload_dict(revocation_list)).encode("utf-8")


def public_key_id(public_key_pem: str) -> str:
    """The stable identifier of a verification key — the same idiom as grants."""
    key = load_pem_public_key(public_key_pem.encode("utf-8"))
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("issuer keys must be Ed25519")
    raw = key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return "ed25519:" + hashlib.sha256(raw).hexdigest()


def build_revocation_list(
    *,
    list_id: str,
    issuer_key_id: str,
    issued_at: str,
    revoked_grant_ids: Sequence[str],
    supersedes: str | None,
    private_key_pem: str,
) -> RevocationList:
    """Build and sign an ADR-052 revocation list. Pure: no clock, no I/O.

    The signing key must match ``issuer_key_id`` — a list must not
    misattribute its issuer, exactly as a grant must not.
    """
    key = load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("issuer keys must be Ed25519")
    actual_id = public_key_id(
        key.public_key()
        .public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        .decode("utf-8")
    )
    if issuer_key_id != actual_id:
        raise ValueError(
            f"list names issuer {issuer_key_id!r} but the signing key is "
            f"{actual_id!r}; the list must not misattribute its issuer"
        )
    unsigned = RevocationList(
        revocation_list_format_version=REVOCATION_LIST_FORMAT_VERSION,
        issuer_key_id=issuer_key_id,
        issued_at=issued_at,
        revoked_grant_ids=tuple(revoked_grant_ids),
        supersedes=supersedes,
        list_id=list_id,
        signature_scheme=SIGNATURE_SCHEME,
        signature="",
    )
    signature = key.sign(signed_bytes(unsigned))
    return unsigned.model_copy(update={"signature": _b64e(signature)})


def verify_revocation_list(
    revocation_list: RevocationList | Mapping[str, Any],
    public_key_pem: str,
    *,
    expected_key_id: str | None = None,
) -> RevocationListVerification:
    """Verify a revocation list's signature and attribution. Pure and offline.

    A structural problem (wrong format, wrong scheme, malformed signature,
    wrong key) is reported as a failure code rather than raised: a verifier
    must produce a denial it can explain, not an exception it cannot.
    Staleness is the redeemer's judgement, not this function's (ADR-052).
    """
    failures: list[str] = []
    doc = _payload_dict(revocation_list)
    signature = (
        revocation_list.signature
        if isinstance(revocation_list, RevocationList)
        else str(revocation_list.get("signature", ""))
    )
    key_id = str(doc.get("issuer_key_id", ""))
    list_id = str(doc.get("list_id", ""))
    scheme = str(doc.get("signature_scheme", ""))

    if doc.get("revocation_list_format_version") != REVOCATION_LIST_FORMAT_VERSION:
        failures.append("unsupported_format_version")

    if expected_key_id is not None and key_id != expected_key_id:
        failures.append("key_id_mismatch")

    signature_valid = False
    if scheme == SIGNATURE_SCHEME:
        try:
            key = load_pem_public_key(public_key_pem.encode("utf-8"))
            key.verify(_b64d(signature), signed_bytes(revocation_list))
            signature_valid = True
        except (InvalidSignature, ValueError):
            signature_valid = False
    else:
        failures.append("unsupported_scheme")
    if not signature_valid:
        failures.append("signature_mismatch")

    return RevocationListVerification(
        valid=not failures,
        signature_valid=signature_valid,
        failure_codes=tuple(failures),
        issuer_key_id=key_id,
        list_id=list_id,
    )


def latest_revocation_list(
    session: Session, issuer_key_id: str
) -> RevocationListRecord | None:
    """The head of an issuer's monotonic list chain, or None before the first.

    The head is found by following ``supersedes`` backwards: it is the stored
    list no other stored list from this issuer supersedes.
    """
    rows = session.scalars(
        select(RevocationListRecord)
        .where(RevocationListRecord.issuer_key_id == issuer_key_id)
        .order_by(RevocationListRecord.list_id)
    ).all()
    superseded = {r.supersedes for r in rows if r.supersedes is not None}
    heads = [r for r in rows if r.list_id not in superseded]
    if len(heads) > 1:
        raise RevocationChainRefused(
            f"issuer {issuer_key_id!r} has {len(heads)} chain heads; the "
            "store is in a state record_revocation_list refuses to create"
        )
    return heads[0] if heads else None


def record_revocation_list(
    session: Session, revocation_list: RevocationList
) -> RevocationListRecord:
    """Persist a signed list, enforcing the monotonic ``supersedes`` chain.

    For an issuer's first list, ``supersedes`` must be null. Every later list
    must name the issuer's current head — a fork, a gap, or a rewrite of
    history is refused, because revocation propagation is only trustworthy if
    the chain a redeemer holds can be checked against one line of descent.
    """
    head = latest_revocation_list(session, revocation_list.issuer_key_id)
    if head is None:
        if revocation_list.supersedes is not None:
            raise RevocationChainRefused(
                f"list {revocation_list.list_id!r} supersedes "
                f"{revocation_list.supersedes!r}, but issuer "
                f"{revocation_list.issuer_key_id!r} has no recorded lists"
            )
    elif revocation_list.supersedes != head.list_id:
        raise RevocationChainRefused(
            f"list {revocation_list.list_id!r} must supersede the issuer's "
            f"current head {head.list_id!r}, not "
            f"{revocation_list.supersedes!r}"
        )

    row = RevocationListRecord(
        list_id=revocation_list.list_id,
        issuer_key_id=revocation_list.issuer_key_id,
        issued_at=revocation_list.issued_at,
        list_json=canonical_json(revocation_list),
        supersedes=revocation_list.supersedes,
    )
    session.add(row)
    session.flush()
    return row
