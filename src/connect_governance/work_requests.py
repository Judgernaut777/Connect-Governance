"""Work Request intake — a governed act, evaluated by the Kernel like any other.

Creating a Work Request is itself an authorization event (R7): the intake
writes no state until the Kernel has rendered an Allowed Decision for
``work_request.create``, and that Decision is recorded with the full evidence,
exactly as every other Decision Record is. There is no privileged creation
path — the founding authority Genesis grants is evaluated through the same
``evaluate_and_record`` path as everything else.

Fail-closed: if the Kernel renders anything other than Allowed, this function
raises :class:`WorkRequestRefused` and nothing the intake touched is persisted.
Atomicity is the caller's transaction: evaluate, record, and write inside one
transaction, and the refusal unwinds all of it.

Nothing here reads a clock. Every instant — the evaluation time, the recording
time — is supplied by the caller, so intake is reproducible in tests and
replayable like every other governed act.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from sqlalchemy.orm import Session

from connect_governance_kernel import Transition, canonical_json

from .decisions import evaluate_and_record
from .db.models import WorkRequest, WorkRequestRevision
from .resolution import build_decision_request

#: The single authority key intake requires (also one of the founding
#: authorities Genesis grants, so the very first Work Request can be created
#: without a bootstrap special case).
REQUIRED_AUTHORITY = "work_request.create"


class WorkRequestRefused(Exception):
    """The Kernel did not Allow this Work Request's creation.

    Nothing is persisted: the caller's transaction rolls back the recorded
    Decision together with any partial intake state.
    """


def create_work_request(
    session: Session,
    *,
    work_request_id: str,
    owner_organization_id: str,
    workspace_id: str,
    created_by_principal_id: str,
    revision_id: str,
    state_revision: str,
    governance: Mapping[str, Any],
    granted_authorities: Sequence[str],
    budget_ceiling_usd: float | None,
    transition_id: str,
    decision_record_id: str,
    recorded_at: str,
    correlation_id: str | None = None,
) -> WorkRequest:
    """Create a Work Request and its first governance revision, if Allowed.

    The Kernel evaluates a ``CreateWorkRequest`` Transition with
    ``required_authority="work_request.create"`` at the caller-supplied
    ``recorded_at`` instant; the Decision Record is persisted with the full
    request and decision. On any outcome other than Allowed, raises
    :class:`WorkRequestRefused` — the Work Request, its revision, and the
    Decision Record must not survive the caller's rollback.

    ``governance`` is the bounded commitment of the first revision. It is
    stored in canonical form so the stored bytes are reproducible; its schema
    is a governance concern, not a persistence one. ``state_revision`` is the
    opaque token identifying this exact governance state, caller-minted like
    every id in the system.
    """
    request = build_decision_request(
        session,
        transition=Transition(
            transition_id=transition_id,
            transition_type="CreateWorkRequest",
            proposed_by_principal_id=created_by_principal_id,
            target_type="WorkRequest",
            target_id=work_request_id,
            operation="create",
            claims={"work_request_id": work_request_id},
        ),
        required_authority=REQUIRED_AUTHORITY,
        evaluation_time=recorded_at,
        correlation_id=correlation_id,
    )
    decision, _record = evaluate_and_record(
        session,
        record_id=decision_record_id,
        request=request,
        recorded_at=recorded_at,
        work_request_id=work_request_id,
    )
    if decision.outcome != "Allowed":
        raise WorkRequestRefused(
            f"Work Request {work_request_id!r} was not created: the Kernel "
            f"rendered {decision.outcome.value!r} for "
            f"{REQUIRED_AUTHORITY!r} (Decision Record {decision_record_id!r})"
        )

    row = WorkRequest(
        id=work_request_id,
        owner_organization_id=owner_organization_id,
        workspace_id=workspace_id,
        created_by_principal_id=created_by_principal_id,
        recorded_at=recorded_at,
        provenance=transition_id,
    )
    session.add(row)
    session.add(
        WorkRequestRevision(
            id=revision_id,
            work_request_id=work_request_id,
            revision_number=1,
            state_revision=state_revision,
            governance_json=canonical_json(governance),
            granted_authorities=canonical_json(tuple(granted_authorities)),
            budget_ceiling_usd=budget_ceiling_usd,
            supersedes_revision_id=None,
            recorded_at=recorded_at,
            provenance=transition_id,
        )
    )
    session.flush()
    return row
