"""Execution-grant issuance: from an Allowed Decision to a signed artifact.

Issuance is an application-layer act (R4): it reads the persisted Decision
Record, refuses anything that is not Allowed, builds the grant payload from
explicit caller-supplied facts, signs it, and stores the artifact immutably
alongside the record that authorized it.

The grant references its originating Decision Record; the Decision Record is
not edited. Records are append-only — history is corrected by new records,
never by mutation (CONSTITUTIONAL_INVARIANTS, "Time and evidence").

Nothing here decides anything. Whether the Transition *should* have been
allowed is the Kernel's question, already answered and replayable in the
Decision Record. Whether the grant is honoured is the provider's question,
answered at the point of effect (R5).
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from connect_governance_grants import (
    ExecutionGrant,
    GrantPayload,
    sign_grant,
)
from connect_governance_kernel import Decision, canonical_json

from .db.models import DecisionRecord, ExecutionGrantRecord


class GrantIssuanceRefused(Exception):
    """Issuance was attempted from a Decision that does not authorize it."""


def issue_grant(
    session: Session,
    *,
    decision_record_id: str,
    grant_id: str,
    private_key_pem: str,
    issuer_key_id: str,
    work_request_id: str,
    work_request_revision: str | None,
    requesting_principal_id: str,
    organization_id: str,
    workspace_id: str,
    provider_id: str,
    permitted_operations: tuple[str, ...],
    issued_at: str,
    not_before: str | None = None,
    not_after: str | None = None,
    argument_constraints: dict | None = None,
    data_classifications: tuple[str, ...] = (),
    budget_limit_usd: float | None = None,
    delegation_depth: int = 0,
    delegation_max_depth: int | None = None,
    correlation_id: str | None = None,
) -> ExecutionGrant:
    """Issue a signed execution grant from an Allowed Decision Record.

    Raises :class:`GrantIssuanceRefused` when the record is missing or its
    outcome is not Allowed. A grant issued against a Denied or
    ApprovalRequired Decision would be an authorization invented outside the
    Kernel — precisely the failure mode the three-layer model exists to
    prevent (ADR-037, ADR-038).

    ``issued_at`` is explicit, like every timestamp in this system: the caller
    owns what "now" means, so issuance stays reproducible in tests and replay.
    """
    row = session.get(DecisionRecord, decision_record_id)
    if row is None:
        raise GrantIssuanceRefused(f"no Decision Record {decision_record_id!r}")
    decision = Decision.model_validate(json.loads(row.decision_json))
    if decision.outcome != "Allowed":
        raise GrantIssuanceRefused(
            f"Decision Record {decision_record_id!r} has outcome "
            f"{decision.outcome.value!r}; grants issue only from Allowed "
            "Decisions (RA v0.2 §7)"
        )

    payload = GrantPayload(
        grant_format_version="1",
        grant_id=grant_id,
        decision_record_id=decision_record_id,
        work_request_id=work_request_id,
        work_request_revision=work_request_revision,
        requesting_principal_id=requesting_principal_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        provider_id=provider_id,
        permitted_operations=tuple(permitted_operations),
        argument_constraints=argument_constraints or {},
        data_classifications=tuple(data_classifications),
        budget_limit_usd=budget_limit_usd,
        delegation_depth=delegation_depth,
        delegation_max_depth=delegation_max_depth,
        policy_versions=tuple(decision.policy_versions),
        kernel_version=decision.kernel_version,
        not_before=not_before,
        not_after=not_after,
        issued_at=issued_at,
        issuer_key_id=issuer_key_id,
        correlation_id=correlation_id if correlation_id is not None else decision.correlation_id,
    )
    grant = sign_grant(payload, private_key_pem)

    session.add(
        ExecutionGrantRecord(
            id=grant_id,
            decision_record_id=decision_record_id,
            grant_json=canonical_json(grant),
            issuer_key_id=issuer_key_id,
            provider_id=provider_id,
            work_request_id=work_request_id,
            issued_at=issued_at,
            not_before=not_before,
            not_after=not_after,
            correlation_id=payload.correlation_id,
        )
    )
    session.flush()
    return grant


def load_grant(session: Session, grant_id: str) -> ExecutionGrant:
    """Rehydrate a stored grant. The artifact round-trips byte-identically."""
    row = session.get(ExecutionGrantRecord, grant_id)
    if row is None:
        raise KeyError(f"no execution grant {grant_id!r}")
    return ExecutionGrant.model_validate(json.loads(row.grant_json))
