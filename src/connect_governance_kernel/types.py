"""The Kernel's input and output contract.

These types are plain data. They carry no behaviour that reaches outside the
process, and no field is populated from an ambient source — the caller resolves
every fact and supplies it explicitly, including ``evaluation_time``.

Scope note (ADR-048/049): this is the R0 scaffold of the contract. Only the
shape needed by the first vertical slice is defined; the full entity model,
transition catalogue, and policy representation are deliberately absent.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field


class Outcome(StrEnum):
    """The three canonical Decision outcomes (Lexicon §2)."""

    ALLOWED = "Allowed"
    DENIED = "Denied"
    APPROVAL_REQUIRED = "ApprovalRequired"


class ReasonCode(StrEnum):
    """Stable, machine-readable reason identifiers.

    These are versioned wire values, not prose. The human-readable explanation
    is a projection built from evidence; stored evidence must never depend
    solely on rendered prose (Reference Architecture v0.2 §6).
    """

    # Structural / schema
    TRANSITION_SCHEMA_INVALID = "transition.schema_invalid"
    EXPECTED_REVISION_STALE = "transition.expected_revision_stale"

    # Identity and authority
    PRINCIPAL_NOT_FOUND = "principal.not_found"
    PRINCIPAL_INACTIVE = "principal.inactive"
    NO_EXPLICIT_AUTHORITY = "authority.none_explicit"
    AUTHORITY_EXPIRED = "authority.expired"
    AUTHORITY_REVOKED = "authority.revoked"

    # Delegation
    DELEGATION_WOULD_EXPAND = "delegation.would_expand_authority"
    DELEGATION_DEPTH_EXCEEDED = "delegation.depth_exceeded"
    DELEGATION_CEILING_EXCEEDED = "delegation.cumulative_ceiling_exceeded"

    # Policy and resources
    POLICY_CONDITION_FAILED = "policy.condition_failed"
    BUDGET_CEILING_EXCEEDED = "budget.ceiling_exceeded"
    DATA_CLASSIFICATION_REFUSED = "classification.refused"

    # Approval
    APPROVAL_TRIGGERED = "approval.required_by_policy"

    # Allow
    PERMITTED = "permitted"


class _Frozen(BaseModel):
    """Immutable, strict, and closed to unknown fields.

    Strictness is deliberate: a Kernel that silently ignores an unrecognized
    input field cannot claim its Decision was evaluated against the inputs the
    caller believed it sent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class Transition(_Frozen):
    """An immutable proposal to change governed state (ADR-019)."""

    transition_id: str
    transition_type: str
    proposed_by_principal_id: str
    target_type: str
    target_id: str | None = None
    operation: str
    claims: Mapping[str, Any] = Field(default_factory=dict)
    expected_state_revision: str | None = None


class AuthorityEvidence(_Frozen):
    """One resolved authority-bearing relationship.

    Resolved by the caller from the organizational graph. The Kernel does not
    traverse a graph or query a store; it evaluates what it is given.
    """

    relationship_id: str
    relationship_type: str
    principal_id: str
    target_id: str
    granted_authorities: Sequence[str] = ()
    effective_from: str | None = None
    effective_until: str | None = None
    revoked_at: str | None = None


class PolicyVersionRef(_Frozen):
    """An exact, immutable Policy version applicable to this evaluation."""

    policy_id: str
    version: str
    content_hash: str | None = None


class DecisionRequest(_Frozen):
    """Everything the Kernel is permitted to consider.

    ``evaluation_time`` is an explicit RFC 3339 string supplied by the caller —
    the Kernel never reads a clock. Historical explanation replays a Decision
    using the state and versions applicable at the original evaluation time.
    """

    transition: Transition
    principal_active: bool
    authority_evidence: Sequence[AuthorityEvidence] = ()
    policy_versions: Sequence[PolicyVersionRef] = ()
    classifications: Mapping[str, str] = Field(default_factory=dict)
    cumulative_state: Mapping[str, float] = Field(default_factory=dict)
    evaluation_time: str
    correlation_id: str | None = None


class Decision(_Frozen):
    """The structured, explainable result of one evaluation.

    Carries the evidence an auditor needs, not an opaque boolean (ADR-023).
    """

    outcome: Outcome
    reason_codes: Sequence[ReasonCode]
    transition_id: str
    kernel_version: str
    evaluated_at: str
    resolved_authorities: Sequence[str] = ()
    policy_versions: Sequence[str] = ()
    satisfied_conditions: Sequence[str] = ()
    failed_conditions: Sequence[str] = ()
    required_approvals: Sequence[str] = ()
    correlation_id: str | None = None
