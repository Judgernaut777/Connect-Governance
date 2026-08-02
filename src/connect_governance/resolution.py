"""State resolution — turning governed state into an explicit Kernel input.

This is the work the Reference Architecture assigns to the *caller*, not the
Kernel (RA v0.2 §6): traverse the graph, load the applicable revisions,
normalize classifications, and hand the Kernel a complete, explicit
``DecisionRequest``.

Keeping this outside the Kernel is what lets the Kernel stay pure. Everything
here touches a database; nothing here decides anything.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from connect_governance_kernel import (
    AuthorityEvidence,
    DecisionRequest,
    Transition,
)

from .db.models import (
    Agent,
    AuthorityRelationship,
    Person,
    WorkRequestRevision,
)


def principal_is_active(session: Session, principal_id: str) -> bool:
    """Resolve identity state for a Person or Agent.

    An unknown principal resolves to inactive rather than raising: the Kernel
    should render an explainable Denied Decision, not have the caller decide by
    exception which requests are worth evaluating.
    """
    person = session.get(Person, principal_id)
    if person is not None:
        return bool(person.active)
    agent = session.get(Agent, principal_id)
    if agent is not None:
        return bool(agent.active)
    return False


def resolve_authority_evidence(
    session: Session, principal_id: str
) -> list[AuthorityEvidence]:
    """Load every explicit authority relationship held by this Principal.

    Time filtering is **not** applied here. Evidence is passed to the Kernel
    intact so the Kernel can distinguish "no authority was ever granted" from
    "authority exists but expired" — two situations an operator must be able to
    tell apart, and which a pre-filtering caller would collapse into one.

    Ordering is by ``id`` so that ``resolved_authorities`` on the Decision is a
    function of the data, not of database iteration order.
    """
    rows = session.scalars(
        select(AuthorityRelationship)
        .where(AuthorityRelationship.principal_id == principal_id)
        .order_by(AuthorityRelationship.id)
    ).all()
    return [
        AuthorityEvidence(
            relationship_id=r.id,
            relationship_type=r.relationship_type,
            principal_id=r.principal_id,
            target_id=r.target_id,
            granted_authorities=tuple(json.loads(r.granted_authorities)),
            effective_from=r.effective_from,
            effective_until=r.effective_until,
            revoked_at=r.revoked_at,
        )
        for r in rows
    ]


def current_state_revision(session: Session, work_request_id: str) -> str | None:
    """The state-revision token of a Work Request's latest governance revision."""
    row = session.scalars(
        select(WorkRequestRevision)
        .where(WorkRequestRevision.work_request_id == work_request_id)
        .order_by(WorkRequestRevision.revision_number.desc())
        .limit(1)
    ).first()
    return row.state_revision if row is not None else None


def build_decision_request(
    session: Session,
    *,
    transition: Transition,
    required_authority: str,
    evaluation_time: str,
    work_request_id: str | None = None,
    policy_versions: tuple = (),
    constraints: tuple = (),
    classifications: dict | None = None,
    cumulative_state: dict | None = None,
    delegation=None,
    correlation_id: str | None = None,
) -> DecisionRequest:
    """Assemble a complete, explicit Kernel input from governed state.

    ``evaluation_time`` is a parameter, never read from a clock here either.
    The caller of *this* function owns the decision of what "now" means, so a
    replay can pass the original instant and get the original answer.
    """
    return DecisionRequest(
        transition=transition,
        principal_active=principal_is_active(
            session, transition.proposed_by_principal_id
        ),
        required_authority=required_authority,
        current_state_revision=(
            current_state_revision(session, work_request_id)
            if work_request_id is not None
            else None
        ),
        authority_evidence=tuple(
            resolve_authority_evidence(session, transition.proposed_by_principal_id)
        ),
        policy_versions=policy_versions,
        constraints=constraints,
        classifications=classifications or {},
        cumulative_state=cumulative_state or {},
        delegation=delegation,
        evaluation_time=evaluation_time,
        correlation_id=correlation_id,
    )
