"""Genesis — the one-time deployment trust root (ADR-042).

A governance system whose authority derives entirely from explicit relationships
still needs a first relationship. Genesis creates it, once, auditably, and then
permanently disables itself.

The design constraint that shapes this module: **bootstrap authority must not be
a special case inside the Kernel's evaluation path.** Genesis writes an ordinary
``AuthorityRelationship`` row. After it returns, nothing in evaluation knows or
cares that the row came from Genesis — ``provenance`` records it for audit and
is never read by the Kernel. There is no "is this the founder?" branch anywhere,
because such a branch would be a permanent, unexplainable exception in a system
whose entire claim is that every Decision is explainable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.models import (
    Agent,
    AuthorityRelationship,
    GenesisRecord,
    Organization,
    Person,
    Workspace,
)

#: Provenance marker written on every row Genesis creates.
GENESIS_PROVENANCE = "genesis"

#: The authority the founding Person receives. Deliberately narrow: enough to
#: govern the first Work Request, not a permanent superuser. Broadening it is a
#: governance decision, not a deployment convenience.
FOUNDING_AUTHORITIES: tuple[str, ...] = (
    "organization.administer",
    "workspace.create",
    "work_request.create",
    "authority.grant",
)


class GenesisRefused(Exception):
    """Genesis was attempted against non-empty state, or a second time."""


@dataclass(frozen=True)
class GenesisRequest:
    """Everything Genesis records about where its authority came from.

    ``deployment_root_fingerprint`` identifies the **external** trust root that
    authorized this deployment. Connect does not mint it and cannot verify it
    here; it records it so that the origin of all subsequent authority is
    auditable rather than anonymous.
    """

    deployment_root_fingerprint: str
    installer: str
    software_version: str
    initial_policy_hash: str
    initial_config_hash: str
    organization_id: str
    organization_name: str
    workspace_id: str
    workspace_name: str
    founding_person_id: str
    founding_person_name: str
    initial_agent_id: str
    initial_agent_name: str
    authority_id: str
    recorded_at: str


@dataclass(frozen=True)
class GenesisResult:
    organization_id: str
    workspace_id: str
    founding_person_id: str
    initial_agent_id: str
    authority_id: str


def genesis_completed(session: Session) -> bool:
    """Has Genesis already run in this deployment?"""
    return session.get(GenesisRecord, 1) is not None


def _state_is_empty(session: Session) -> bool:
    """True only when no governed state exists at all.

    Checked across every governed table, not just the Genesis record: a
    deployment that somehow acquired an Organization without a Genesis record is
    in an unexplained state, and initializing a trust root into it would bless
    whatever is already there.
    """
    for model in (Organization, Workspace, Person, Agent, AuthorityRelationship):
        if session.scalar(select(model).limit(1)) is not None:
            return False
    return not genesis_completed(session)


def initialize_deployment(session: Session, request: GenesisRequest) -> GenesisResult:
    """Establish the deployment trust root. Valid only against empty state.

    Raises :class:`GenesisRefused` if any governed state exists or Genesis has
    already run. The refusal is deliberately not idempotent-success: a second
    Genesis attempt against a live deployment is a serious operational event and
    must be surfaced, not silently absorbed.
    """
    if genesis_completed(session):
        raise GenesisRefused(
            "Genesis has already completed for this deployment; the bootstrap "
            "path is permanently disabled (ADR-042)"
        )
    if not _state_is_empty(session):
        raise GenesisRefused(
            "governed state already exists; Genesis is valid only against empty "
            "state and will not adopt pre-existing entities (ADR-042)"
        )

    session.add(
        Organization(
            id=request.organization_id,
            name=request.organization_name,
            recorded_at=request.recorded_at,
            provenance=GENESIS_PROVENANCE,
        )
    )
    session.add(
        Workspace(
            id=request.workspace_id,
            organization_id=request.organization_id,
            name=request.workspace_name,
            recorded_at=request.recorded_at,
            provenance=GENESIS_PROVENANCE,
        )
    )
    session.add(
        Person(
            id=request.founding_person_id,
            display_name=request.founding_person_name,
            active=True,
            recorded_at=request.recorded_at,
            provenance=GENESIS_PROVENANCE,
        )
    )
    session.add(
        Agent(
            id=request.initial_agent_id,
            display_name=request.initial_agent_name,
            active=True,
            recorded_at=request.recorded_at,
            provenance=GENESIS_PROVENANCE,
        )
    )

    # An ORDINARY authority row. Nothing downstream treats it specially.
    session.add(
        AuthorityRelationship(
            id=request.authority_id,
            relationship_type="GenesisGrant",
            principal_id=request.founding_person_id,
            target_id=request.organization_id,
            granted_authorities=json.dumps(list(FOUNDING_AUTHORITIES)),
            effective_from=request.recorded_at,
            effective_until=None,
            revoked_at=None,
            recorded_at=request.recorded_at,
            provenance=GENESIS_PROVENANCE,
        )
    )

    session.add(
        GenesisRecord(
            singleton=1,
            deployment_root_fingerprint=request.deployment_root_fingerprint,
            installer=request.installer,
            software_version=request.software_version,
            initial_policy_hash=request.initial_policy_hash,
            initial_config_hash=request.initial_config_hash,
            founding_person_id=request.founding_person_id,
            initial_organization_id=request.organization_id,
            initial_authority_id=request.authority_id,
            recorded_at=request.recorded_at,
        )
    )
    session.flush()

    return GenesisResult(
        organization_id=request.organization_id,
        workspace_id=request.workspace_id,
        founding_person_id=request.founding_person_id,
        initial_agent_id=request.initial_agent_id,
        authority_id=request.authority_id,
    )
