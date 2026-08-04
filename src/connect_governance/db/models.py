"""Governed state for the vertical slice.

Only the entities ADR-048 requires. This is deliberately **not** the full domain
model: no Roles, no Role Assignments, no Fulfillment Policies, no Budgets as
first-class entities, no Policy registry. Those arrive when a milestone needs
them, not because the Reference Architecture lists them.

Two distinctions the schema enforces rather than documents:

* **Ownership is not containment.** A Work Request is *owned* by exactly one
  Owner Container (Organization) and *contained* by a Workspace. Both columns
  exist because collapsing them would encode the conflation the Lexicon
  explicitly prohibits (ADR-003, ADR-011).
* **Governance is versioned; operations are mutable.** Work Request identity is
  stable while every governance change creates a new immutable revision
  (ADR-012). Revisions are append-only — there is no update path.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Organization(Base):
    """An Owner Container. Owns durable objects; does not own Persons."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String, nullable=False)
    #: How this row came to exist: "genesis" or a transition id.
    provenance: Mapped[str] = mapped_column(String, nullable=False)


class Workspace(Base):
    """The primary operating environment. Contains work; does not own it."""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[str] = mapped_column(String, nullable=False)


class Person(Base):
    """A first-class human identity. Organizations own Membership, not Persons."""

    __tablename__ = "persons"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    recorded_at: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[str] = mapped_column(String, nullable=False)


class Agent(Base):
    """A governed organizational actor, separate from any Execution (ADR-005)."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    recorded_at: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[str] = mapped_column(String, nullable=False)


class AuthorityRelationship(Base):
    """Explicit authority. The only source of authority there is.

    The Kernel receives these as ``AuthorityEvidence``. Nothing distinguishes an
    authority created by Genesis from one created by a later Transition once it
    is written — the difference is recorded in ``provenance`` for audit, and is
    invisible to evaluation. That is deliberate: bootstrap must not become a
    special case inside the evaluation path.
    """

    __tablename__ = "authority_relationships"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)
    principal_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    #: JSON array of authority keys.
    granted_authorities: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[str | None] = mapped_column(String, nullable=True)
    effective_until: Mapped[str | None] = mapped_column(String, nullable=True)
    revoked_at: Mapped[str | None] = mapped_column(String, nullable=True)
    recorded_at: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[str] = mapped_column(String, nullable=False)


class WorkRequest(Base):
    """A governed organizational commitment for bounded work.

    Not a task, prompt, workflow, plan, or intent (ADR-010). Identity is stable;
    governance lives in revisions.
    """

    __tablename__ = "work_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    #: Ownership — exactly one Owner Container (ADR-003).
    owner_organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    #: Containment — operational placement, NOT ownership (ADR-011).
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    created_by_principal_id: Mapped[str] = mapped_column(String, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[str] = mapped_column(String, nullable=False)


class WorkRequestRevision(Base):
    """An immutable version of a Work Request's governance state (ADR-012).

    Append-only. A governance change writes a new revision; it never edits one.
    ``state_revision`` is the token the Kernel compares against a Transition's
    ``expected_state_revision`` for optimistic concurrency.
    """

    __tablename__ = "work_request_revisions"
    __table_args__ = (
        UniqueConstraint("work_request_id", "revision_number", name="uq_wrr_number"),
        UniqueConstraint("state_revision", name="uq_wrr_state_revision"),
        CheckConstraint("revision_number >= 1", name="ck_wrr_number_positive"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    work_request_id: Mapped[str] = mapped_column(
        ForeignKey("work_requests.id"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Opaque token identifying this exact governance state.
    state_revision: Mapped[str] = mapped_column(String, nullable=False)
    #: The bounded commitment: JSON. Kept opaque here — its schema is a
    #: governance concern, not a persistence one.
    governance_json: Mapped[str] = mapped_column(Text, nullable=False)
    #: Maximum autonomous operating boundary, as authority keys (JSON array).
    granted_authorities: Mapped[str] = mapped_column(Text, nullable=False)
    budget_ceiling_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    supersedes_revision_id: Mapped[str | None] = mapped_column(String, nullable=True)
    recorded_at: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[str] = mapped_column(String, nullable=False)


class GenesisRecord(Base):
    """The one-time deployment trust root (ADR-042).

    Its existence is what disables the bootstrap path: Genesis refuses to run a
    second time because this row is present. A single-row table constraint makes
    that structural rather than procedural.
    """

    __tablename__ = "genesis_record"
    __table_args__ = (
        CheckConstraint("singleton = 1", name="ck_genesis_singleton"),
    )

    singleton: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    #: Fingerprint of the EXTERNAL deployment trust root that initiated Genesis.
    deployment_root_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    installer: Mapped[str] = mapped_column(String, nullable=False)
    software_version: Mapped[str] = mapped_column(String, nullable=False)
    initial_policy_hash: Mapped[str] = mapped_column(String, nullable=False)
    initial_config_hash: Mapped[str] = mapped_column(String, nullable=False)
    founding_person_id: Mapped[str] = mapped_column(String, nullable=False)
    initial_organization_id: Mapped[str] = mapped_column(String, nullable=False)
    initial_authority_id: Mapped[str] = mapped_column(String, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String, nullable=False)


class DecisionRecord(Base):
    """Immutable evidence of one authorization Decision (ADR-024).

    Stores the **complete** request and decision in canonical form. Replay is
    therefore possible without reconstructing state: re-evaluate the stored
    request and compare bytes.

    The human-readable explanation is deliberately **not** stored. It is a
    projection built on read from this structured evidence; storing rendered
    prose would make the record depend on the wording of the day it was written.
    """

    __tablename__ = "decision_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    transition_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String, nullable=False, index=True)
    #: Canonical JSON of the exact DecisionRequest that was evaluated.
    request_json: Mapped[str] = mapped_column(Text, nullable=False)
    #: Canonical JSON of the exact Decision that was returned.
    decision_json: Mapped[str] = mapped_column(Text, nullable=False)
    kernel_version: Mapped[str] = mapped_column(String, nullable=False)
    conformance_spec_version: Mapped[str] = mapped_column(String, nullable=False)
    evaluated_at: Mapped[str] = mapped_column(String, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    work_request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    work_request_revision: Mapped[str | None] = mapped_column(String, nullable=True)


class ExecutionGrantRecord(Base):
    """Immutable record of one issued execution grant (R4, ADR-038).

    Stores the complete signed artifact in canonical form — payload plus
    signature — so a later verifier can reproduce the exact signed bytes
    without trusting a re-serialization. The record references its originating
    Decision Record; neither is ever edited after issuance.
    """

    __tablename__ = "execution_grant_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    #: The Decision Record whose Allowed outcome authorized this grant.
    decision_record_id: Mapped[str] = mapped_column(
        ForeignKey("decision_records.id"), nullable=False, index=True
    )
    #: Canonical JSON of the complete ExecutionGrant (payload + signature).
    grant_json: Mapped[str] = mapped_column(Text, nullable=False)
    issuer_key_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    work_request_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    issued_at: Mapped[str] = mapped_column(String, nullable=False)
    not_before: Mapped[str | None] = mapped_column(String, nullable=True)
    not_after: Mapped[str | None] = mapped_column(String, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
