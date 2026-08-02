"""The Decision Kernel's single entry point.

``evaluate()`` is a pure function. Given identical inputs it returns an
identical Decision, on any machine, at any wall-clock time, in any process.
It reads no clock, generates no randomness, touches no store, and holds no
state between calls.

The evaluation order below is **normative**. It is part of the conformance
contract, not an implementation detail: two conformant implementations must
emit the same ``reason_codes``, ``satisfied_conditions``, and
``failed_conditions`` *sequences*, not merely the same sets. See
``docs/CONFORMANCE.md``.

Evaluation does not short-circuit. Every stage runs and contributes evidence,
because an operator asking "why was this denied?" is badly served by an answer
that stops at the first problem. Outcome is decided from the accumulated
evidence at the end.
"""

from __future__ import annotations

from typing import Sequence

from .types import (
    AuthorityEvidence,
    BudgetCeiling,
    Decision,
    DecisionRequest,
    ForbidClassification,
    Outcome,
    ReasonCode,
    RequireApproval,
    RequireClassification,
    parse_rfc3339,
)

KERNEL_VERSION = "0.0.1"

#: Normative stage order. Stages run in this sequence and evidence is appended
#: in the order produced.
STAGE_ORDER: tuple[str, ...] = (
    "structural",
    "principal",
    "authority",
    "delegation",
    "constraints",
    "approval",
)


def _authority_is_effective(
    ev: AuthorityEvidence, at: str
) -> tuple[bool, ReasonCode | None]:
    """Is this evidence in force at ``at``?

    Window semantics are half-open: ``effective_from <= t < effective_until``.
    A revocation at exactly ``t`` is in force — revocation is protective, so
    the boundary resolves against the actor. Both rules are fixed by the
    conformance vectors and may not be reinterpreted by an implementation.
    """
    t = parse_rfc3339(at)

    if ev.revoked_at is not None and parse_rfc3339(ev.revoked_at) <= t:
        return False, ReasonCode.AUTHORITY_REVOKED
    if ev.effective_from is not None and t < parse_rfc3339(ev.effective_from):
        return False, ReasonCode.AUTHORITY_NOT_YET_EFFECTIVE
    if ev.effective_until is not None and t >= parse_rfc3339(ev.effective_until):
        return False, ReasonCode.AUTHORITY_EXPIRED
    return True, None


def evaluate(request: DecisionRequest) -> Decision:
    """Evaluate a proposed Transition and return a deterministic Decision."""
    reasons: list[ReasonCode] = []
    satisfied: list[str] = []
    failed: list[str] = []
    resolved: list[str] = []
    approvals: list[str] = []

    # --- Stage 1: structural -----------------------------------------------
    # A Decision evaluated against stale state must never silently apply to
    # incompatible current state. The Kernel refuses; it does not reconcile.
    if (
        request.transition.expected_state_revision is not None
        and request.current_state_revision is not None
        and request.transition.expected_state_revision != request.current_state_revision
    ):
        reasons.append(ReasonCode.EXPECTED_REVISION_STALE)
        failed.append("structural.expected_revision_matches")
    else:
        satisfied.append("structural.expected_revision_matches")

    # --- Stage 2: principal -------------------------------------------------
    if request.principal_active:
        satisfied.append("principal.active")
    else:
        reasons.append(ReasonCode.PRINCIPAL_INACTIVE)
        failed.append("principal.active")

    # --- Stage 3: authority -------------------------------------------------
    # Authority derives ONLY from explicit relationships that grant the exact
    # required key and are in force at evaluation_time. Structure grants
    # nothing; nothing here infers authority from containment or hierarchy.
    candidates = [
        ev
        for ev in request.authority_evidence
        if ev.principal_id == request.transition.proposed_by_principal_id
        and request.required_authority in ev.granted_authorities
    ]

    effective: list[AuthorityEvidence] = []
    ineffective_reasons: list[ReasonCode] = []
    for ev in candidates:
        ok, why = _authority_is_effective(ev, request.evaluation_time)
        if ok:
            effective.append(ev)
        elif why is not None and why not in ineffective_reasons:
            ineffective_reasons.append(why)

    if effective:
        satisfied.append("authority.explicit_and_effective")
        resolved.extend(ev.relationship_id for ev in effective)
    else:
        failed.append("authority.explicit_and_effective")
        if candidates:
            # Authority exists on paper but is not in force. Report why, in
            # the fixed order revoked -> not-yet-effective -> expired, so the
            # sequence is reproducible when several candidates fail differently.
            for code in (
                ReasonCode.AUTHORITY_REVOKED,
                ReasonCode.AUTHORITY_NOT_YET_EFFECTIVE,
                ReasonCode.AUTHORITY_EXPIRED,
            ):
                if code in ineffective_reasons:
                    reasons.append(code)
        else:
            reasons.append(ReasonCode.NO_EXPLICIT_AUTHORITY)

    # --- Stage 4: delegation ------------------------------------------------
    # Delegated work may preserve or narrow authority, never expand it
    # (ADR-015), and depth is bounded (ADR-016).
    d = request.delegation
    if d is not None:
        if d.max_depth is not None and d.depth > d.max_depth:
            reasons.append(ReasonCode.DELEGATION_DEPTH_EXCEEDED)
            failed.append("delegation.within_depth")
        else:
            satisfied.append("delegation.within_depth")

        if request.required_authority in d.granting_authorities:
            satisfied.append("delegation.subset_of_grant")
        else:
            reasons.append(ReasonCode.DELEGATION_WOULD_EXPAND)
            failed.append("delegation.subset_of_grant")

    # --- Stage 5: constraints -----------------------------------------------
    # A closed vocabulary of normalized declarative facts. No expressions, no
    # interpretation. Evaluated in the order the caller supplied them, so the
    # evidence sequence is a function of the input alone.
    for c in request.constraints:
        if isinstance(c, RequireClassification):
            if request.classifications.get(c.key) == c.value:
                satisfied.append(c.constraint_id)
            else:
                reasons.append(ReasonCode.CLASSIFICATION_REQUIRED)
                failed.append(c.constraint_id)
        elif isinstance(c, ForbidClassification):
            if request.classifications.get(c.key) == c.value:
                reasons.append(ReasonCode.CLASSIFICATION_FORBIDDEN)
                failed.append(c.constraint_id)
            else:
                satisfied.append(c.constraint_id)
        elif isinstance(c, BudgetCeiling):
            # Ceilings are cumulative across derived work (ADR-016) and are
            # exceeded strictly above the limit: spend == limit is permitted.
            if request.cumulative_state.get(c.key, 0.0) > c.limit:
                reasons.append(ReasonCode.BUDGET_CEILING_EXCEEDED)
                failed.append(c.constraint_id)
            else:
                satisfied.append(c.constraint_id)
        elif isinstance(c, RequireApproval):
            approvals.append(c.approval_id)

    # --- Stage 6: approval --------------------------------------------------
    # Approval satisfies a policy-defined condition; it never overrides
    # authority (ADR-026). A missing authority is therefore always a denial,
    # never something an approver can wave through.
    if approvals:
        reasons.append(ReasonCode.APPROVAL_TRIGGERED)

    # --- Outcome ------------------------------------------------------------
    denied = bool(failed)
    if denied:
        outcome = Outcome.DENIED
    elif approvals:
        outcome = Outcome.APPROVAL_REQUIRED
    else:
        outcome = Outcome.ALLOWED
        reasons.append(ReasonCode.PERMITTED)

    return Decision(
        outcome=outcome,
        reason_codes=tuple(reasons),
        transition_id=request.transition.transition_id,
        kernel_version=KERNEL_VERSION,
        evaluated_at=request.evaluation_time,
        resolved_authorities=tuple(resolved),
        policy_versions=tuple(
            f"{p.policy_id}@{p.version}" for p in request.policy_versions
        ),
        satisfied_conditions=tuple(satisfied),
        failed_conditions=tuple(failed),
        required_approvals=tuple(approvals),
        correlation_id=request.correlation_id,
    )


__all__ = ["evaluate", "KERNEL_VERSION", "STAGE_ORDER"]
