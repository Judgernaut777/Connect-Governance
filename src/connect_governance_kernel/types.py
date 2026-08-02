"""The Kernel's input and output contract.

These types are plain data. They carry no behaviour that reaches outside the
process, and no field is populated from an ambient source — the caller resolves
every fact and supplies it explicitly, including ``evaluation_time``.

Scope note (ADR-048/049): only the shape the first vertical slice needs is
defined. There is deliberately no policy *language* here. Constraints arrive as
a small closed vocabulary of normalized declarative facts; the Kernel evaluates
them, it does not parse or interpret expressions.

Timestamps are RFC 3339. Comparison semantics are specified in
``docs/CONFORMANCE.md`` and are part of the conformance contract, not an
implementation detail.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Mapping, Sequence, Union

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
    solely on rendered prose.
    """

    # Structural / schema
    EXPECTED_REVISION_STALE = "transition.expected_revision_stale"

    # Identity and authority
    PRINCIPAL_INACTIVE = "principal.inactive"
    NO_EXPLICIT_AUTHORITY = "authority.none_explicit"
    AUTHORITY_NOT_YET_EFFECTIVE = "authority.not_yet_effective"
    AUTHORITY_EXPIRED = "authority.expired"
    AUTHORITY_REVOKED = "authority.revoked"

    # Delegation
    DELEGATION_WOULD_EXPAND = "delegation.would_expand_authority"
    DELEGATION_DEPTH_EXCEEDED = "delegation.depth_exceeded"

    # Policy constraints and resources
    CLASSIFICATION_REQUIRED = "classification.required_absent"
    CLASSIFICATION_FORBIDDEN = "classification.forbidden_present"
    BUDGET_CEILING_EXCEEDED = "budget.ceiling_exceeded"

    # Approval
    APPROVAL_TRIGGERED = "approval.required_by_policy"

    # Allow
    PERMITTED = "permitted"


def parse_rfc3339(value: str) -> datetime:
    """Parse an RFC 3339 timestamp to an aware datetime.

    Pure: this reads no clock. ``Z`` is normalized to ``+00:00`` because
    :func:`datetime.fromisoformat` accepts the offset form on every supported
    version. A value without an offset is rejected rather than assumed to be
    UTC — silently guessing a timezone would make a Decision depend on a fact
    the caller never supplied.
    """
    text = value.strip()
    if text.endswith(("z", "Z")):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must carry a UTC offset: {value!r}")
    return parsed


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
    traverse a graph or query a store; it evaluates what it is given. Authority
    derives only from explicit relationships, never from structure.
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


class DelegationContext(_Frozen):
    """Bounds on delegated work creation (ADR-013, ADR-015, ADR-016).

    ``granting_authorities`` is the authority set of the grant this Transition
    is derived from. Delegated work may preserve or narrow authority; it may
    never expand it.
    """

    depth: int = 0
    max_depth: int | None = None
    granting_authorities: Sequence[str] = ()


# --- Constraints: a closed vocabulary, not a policy language ----------------
#
# Each constraint is a normalized declarative fact resolved by the caller from
# an immutable Policy version. There are no expressions, no operators, and no
# user-authored predicates — adding a constraint kind is a deliberate,
# versioned change to this contract, not a configuration change.


class _Constraint(_Frozen):
    constraint_id: str
    policy_version: str


class RequireClassification(_Constraint):
    kind: Literal["require_classification"] = "require_classification"
    key: str
    value: str


class ForbidClassification(_Constraint):
    kind: Literal["forbid_classification"] = "forbid_classification"
    key: str
    value: str


class BudgetCeiling(_Constraint):
    kind: Literal["budget_ceiling"] = "budget_ceiling"
    key: str
    limit: float


class RequireApproval(_Constraint):
    kind: Literal["require_approval"] = "require_approval"
    approval_id: str


Constraint = Annotated[
    Union[RequireClassification, ForbidClassification, BudgetCeiling, RequireApproval],
    Field(discriminator="kind"),
]


class DecisionRequest(_Frozen):
    """Everything the Kernel is permitted to consider.

    ``evaluation_time`` is an explicit RFC 3339 string supplied by the caller —
    the Kernel never reads a clock. Historical explanation replays a Decision
    using the state and versions applicable at the original evaluation time.

    ``required_authority`` is the single authority key this Transition needs,
    already normalized by the caller against an authoritative registry. The
    Kernel does not infer required authority from the transition type; that
    inference is state resolution and belongs outside the Kernel.
    """

    transition: Transition
    principal_active: bool
    required_authority: str
    current_state_revision: str | None = None
    authority_evidence: Sequence[AuthorityEvidence] = ()
    policy_versions: Sequence[PolicyVersionRef] = ()
    constraints: Sequence[Constraint] = ()
    classifications: Mapping[str, str] = Field(default_factory=dict)
    cumulative_state: Mapping[str, float] = Field(default_factory=dict)
    delegation: DelegationContext | None = None
    evaluation_time: str
    correlation_id: str | None = None


class Decision(_Frozen):
    """The structured, explainable result of one evaluation.

    Carries the evidence an auditor needs, not an opaque boolean (ADR-023).
    ``satisfied_conditions`` and ``failed_conditions`` are emitted in the
    Kernel's fixed evaluation order so that two conformant implementations
    produce identical sequences, not merely identical sets.
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
