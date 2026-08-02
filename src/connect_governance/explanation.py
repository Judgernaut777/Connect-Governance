"""Explanation — a projection over structured evidence, never the record itself.

Two views, per R3:

* :func:`operator_view` — outcome, a plain-language reason, the material limit
  or failure, and the required next action. Four fields, because an operator
  deciding what to do next is not helped by twelve.
* :func:`proof_view` — the ordered evaluation stages, stable reason codes,
  authorities evaluated, constraints and their results, approval findings, the
  applicable revisions, and the Kernel and specification versions.

Both are computed on read from ``(DecisionRequest, Decision)``. Nothing here is
persisted. This is the whole point: prose is a rendering of evidence, and
evidence must never be recoverable only from prose. Reword any sentence in this
module and no stored record changes.

The hard problem this module only partly solves: the proof view is an expert
artifact, and the product's stated audience is non-technical operators. The
operator view is the first attempt at that translation, not a finished answer.
"""

from __future__ import annotations

from typing import Any, Mapping

from connect_governance_kernel import (
    BudgetCeiling,
    Decision,
    DecisionRequest,
    ForbidClassification,
    Outcome,
    ReasonCode,
    RequireApproval,
    RequireClassification,
)
from connect_governance_kernel.evaluate import STAGE_ORDER

CONFORMANCE_SPEC_VERSION = "1"

#: One plain sentence per reason code. A projection detail: changing a sentence
#: is a wording change, never a change to what was decided.
_REASON_PROSE: Mapping[ReasonCode, str] = {
    ReasonCode.EXPECTED_REVISION_STALE: (
        "The work changed after this request was prepared, so it was not applied "
        "to the newer version."
    ),
    ReasonCode.PRINCIPAL_INACTIVE: "The requester's account is not active.",
    ReasonCode.NO_EXPLICIT_AUTHORITY: (
        "The requester has not been granted the permission this action needs."
    ),
    ReasonCode.AUTHORITY_NOT_YET_EFFECTIVE: (
        "The requester's permission has been granted but does not start until later."
    ),
    ReasonCode.AUTHORITY_EXPIRED: "The requester's permission has expired.",
    ReasonCode.AUTHORITY_REVOKED: "The requester's permission was revoked.",
    ReasonCode.DELEGATION_WOULD_EXPAND: (
        "This would give the delegated work more permission than the work it came "
        "from, which is never allowed."
    ),
    ReasonCode.DELEGATION_DEPTH_EXCEEDED: (
        "Work has been delegated too many times in a chain."
    ),
    ReasonCode.CLASSIFICATION_REQUIRED: (
        "The data classification required by policy is missing or different."
    ),
    ReasonCode.CLASSIFICATION_FORBIDDEN: (
        "The data involved is classified in a way policy forbids for this action."
    ),
    ReasonCode.BUDGET_CEILING_EXCEEDED: "This would exceed the spending limit.",
    ReasonCode.APPROVAL_TRIGGERED: "This needs a human approval before it can proceed.",
    ReasonCode.PERMITTED: "Permitted.",
}

#: Which stage a condition identifier belongs to. Derived from the documented
#: stage order rather than stored on the Decision, so the canonical record shape
#: is unchanged by the existence of this view.
_CONDITION_PREFIX_STAGE: tuple[tuple[str, str], ...] = (
    ("structural.", "structural"),
    ("principal.", "principal"),
    ("authority.", "authority"),
    ("delegation.", "delegation"),
)


def _stage_for_condition(condition: str, constraint_ids: set[str]) -> str:
    if condition in constraint_ids:
        return "constraints"
    for prefix, stage in _CONDITION_PREFIX_STAGE:
        if condition.startswith(prefix):
            return stage
    return "constraints"


def _material_finding(request: DecisionRequest, decision: Decision) -> str | None:
    """The specific limit or fact that decided it — numbers, not adjectives.

    An operator told "budget exceeded" still has to go find the numbers. An
    operator told "spend 120.00 exceeds the limit of 100.00" is done reading.
    """
    failed = set(decision.failed_conditions)

    for c in request.constraints:
        if c.constraint_id not in failed:
            continue
        if isinstance(c, BudgetCeiling):
            actual = request.cumulative_state.get(c.key, 0.0)
            return (
                f"{c.key}: {actual:g} committed against a limit of {c.limit:g} "
                f"(policy {c.policy_version})"
            )
        if isinstance(c, RequireClassification):
            actual = request.classifications.get(c.key)
            observed = repr(actual) if actual is not None else "not set"
            return (
                f"{c.key} must be {c.value!r}; it is {observed} "
                f"(policy {c.policy_version})"
            )
        if isinstance(c, ForbidClassification):
            return (
                f"{c.key} is {c.value!r}, which policy {c.policy_version} forbids "
                "for this action"
            )

    if "authority.explicit_and_effective" in failed:
        return f"required permission: {request.required_authority}"

    if "delegation.within_depth" in failed and request.delegation is not None:
        return (
            f"delegation depth {request.delegation.depth} exceeds the maximum of "
            f"{request.delegation.max_depth}"
        )

    if "delegation.subset_of_grant" in failed and request.delegation is not None:
        return (
            f"{request.required_authority} is not among the permissions the "
            "originating work was granted"
        )

    if "structural.expected_revision_matches" in failed:
        return (
            f"prepared against version {request.transition.expected_state_revision}; "
            f"current version is {request.current_state_revision}"
        )

    return None


def _next_action(request: DecisionRequest, decision: Decision) -> str:
    """What the operator should actually do. Never 'contact an administrator'."""
    codes = set(decision.reason_codes)

    if decision.outcome is Outcome.ALLOWED:
        return "No action needed — this is authorized and may proceed."

    if decision.outcome is Outcome.APPROVAL_REQUIRED:
        approvals = ", ".join(decision.required_approvals)
        return f"Request approval to proceed ({approvals})."

    if ReasonCode.EXPECTED_REVISION_STALE in codes:
        return "Reload the work and submit again against its current version."
    if ReasonCode.PRINCIPAL_INACTIVE in codes:
        return "Reactivate the requester's account, then submit again."
    if ReasonCode.AUTHORITY_EXPIRED in codes or ReasonCode.AUTHORITY_REVOKED in codes:
        return (
            f"Have {request.required_authority} granted again to "
            f"{request.transition.proposed_by_principal_id}, then submit again."
        )
    if ReasonCode.AUTHORITY_NOT_YET_EFFECTIVE in codes:
        return "Wait until the granted permission starts, then submit again."
    if ReasonCode.NO_EXPLICIT_AUTHORITY in codes:
        return (
            f"Grant {request.required_authority} to "
            f"{request.transition.proposed_by_principal_id}, then submit again."
        )
    if ReasonCode.DELEGATION_WOULD_EXPAND in codes:
        return (
            "Narrow this work to the permissions the originating work already has, "
            "or raise it as a new governed request."
        )
    if ReasonCode.DELEGATION_DEPTH_EXCEEDED in codes:
        return "Raise this as a new governed request rather than a further delegation."
    if ReasonCode.BUDGET_CEILING_EXCEEDED in codes:
        return "Raise the spending limit through a governed change, or reduce the scope."
    if ReasonCode.CLASSIFICATION_REQUIRED in codes or (
        ReasonCode.CLASSIFICATION_FORBIDDEN in codes
    ):
        return "Correct the data classification, or raise a governed policy exception."

    return "Review the proof view for the failed conditions."


def operator_view(request: DecisionRequest, decision: Decision) -> dict[str, Any]:
    """The concise view: outcome, reason, material finding, next action."""
    if decision.outcome is Outcome.ALLOWED:
        reason = "Permitted: the requester holds the required permission and no limit was exceeded."
    else:
        # The first non-`permitted` code is the headline; the rest are detail
        # the proof view carries. Order is the Kernel's normative stage order,
        # so the headline is the earliest-stage problem, which is the one that
        # usually has to be fixed first.
        headline = next(
            (c for c in decision.reason_codes if c is not ReasonCode.PERMITTED), None
        )
        reason = _REASON_PROSE.get(headline, "See the proof view.") if headline else ""

    return {
        "outcome": decision.outcome.value,
        "reason": reason,
        "material_finding": _material_finding(request, decision),
        "next_action": _next_action(request, decision),
    }


def proof_view(request: DecisionRequest, decision: Decision) -> dict[str, Any]:
    """The expandable view: the complete evidence, grouped by evaluation stage."""
    constraint_ids = {c.constraint_id for c in request.constraints}
    satisfied = set(decision.satisfied_conditions)
    failed = set(decision.failed_conditions)

    stages: list[dict[str, Any]] = []
    for stage in STAGE_ORDER:
        stage_satisfied = [
            c
            for c in decision.satisfied_conditions
            if _stage_for_condition(c, constraint_ids) == stage
        ]
        stage_failed = [
            c
            for c in decision.failed_conditions
            if _stage_for_condition(c, constraint_ids) == stage
        ]
        if stage == "approval":
            evaluated = bool(decision.required_approvals)
        else:
            evaluated = bool(stage_satisfied or stage_failed)
        stages.append(
            {
                "stage": stage,
                "evaluated": evaluated,
                "satisfied": stage_satisfied,
                "failed": stage_failed,
            }
        )

    authorities = []
    for ev in request.authority_evidence:
        relied_on = ev.relationship_id in decision.resolved_authorities
        matched_principal = (
            ev.principal_id == request.transition.proposed_by_principal_id
        )
        grants_required = request.required_authority in ev.granted_authorities
        authorities.append(
            {
                "relationship_id": ev.relationship_id,
                "relationship_type": ev.relationship_type,
                "principal_id": ev.principal_id,
                "target_id": ev.target_id,
                "granted_authorities": list(ev.granted_authorities),
                "matches_principal": matched_principal,
                "grants_required_authority": grants_required,
                "was_a_candidate": matched_principal and grants_required,
                "relied_upon": relied_on,
                "effective_from": ev.effective_from,
                "effective_until": ev.effective_until,
                "revoked_at": ev.revoked_at,
            }
        )

    constraints = []
    for c in request.constraints:
        entry: dict[str, Any] = {
            "constraint_id": c.constraint_id,
            "kind": c.kind,
            "policy_version": c.policy_version,
        }
        if isinstance(c, BudgetCeiling):
            entry |= {
                "key": c.key,
                "limit": c.limit,
                "observed": request.cumulative_state.get(c.key, 0.0),
            }
        elif isinstance(c, (RequireClassification, ForbidClassification)):
            entry |= {
                "key": c.key,
                "value": c.value,
                "observed": request.classifications.get(c.key),
            }
        elif isinstance(c, RequireApproval):
            entry |= {"approval_id": c.approval_id}
        entry["result"] = (
            "satisfied"
            if c.constraint_id in satisfied
            else "failed"
            if c.constraint_id in failed
            else "not_a_gate"
        )
        constraints.append(entry)

    return {
        "outcome": decision.outcome.value,
        "reason_codes": [c.value for c in decision.reason_codes],
        "stages": stages,
        "authorities_evaluated": authorities,
        "constraints_evaluated": constraints,
        "approval_findings": {
            "required": list(decision.required_approvals),
            "triggered": bool(decision.required_approvals),
            "note": (
                "Approval satisfies a policy condition; it never overrides authority "
                "(ADR-026)."
            ),
        },
        "revisions": {
            "transition_id": decision.transition_id,
            "expected_state_revision": request.transition.expected_state_revision,
            "current_state_revision": request.current_state_revision,
            "policy_versions": list(decision.policy_versions),
        },
        "versions": {
            "kernel_version": decision.kernel_version,
            "conformance_spec_version": CONFORMANCE_SPEC_VERSION,
        },
        "evaluated_at": decision.evaluated_at,
        "correlation_id": decision.correlation_id,
    }


def explain(request: DecisionRequest, decision: Decision) -> dict[str, Any]:
    """Both views together, for a UI that shows one and expands into the other."""
    return {
        "operator": operator_view(request, decision),
        "proof": proof_view(request, decision),
    }
