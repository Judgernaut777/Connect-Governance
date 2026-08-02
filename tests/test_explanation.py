"""Explanation is a projection: derived on read, never stored, never canonical."""

from __future__ import annotations

import json

import pytest

from connect_governance.explanation import explain, operator_view, proof_view
from connect_governance_kernel import (
    AuthorityEvidence,
    BudgetCeiling,
    DecisionRequest,
    RequireApproval,
    Transition,
    evaluate,
)
from connect_governance_kernel.evaluate import STAGE_ORDER

T = "2026-08-03T12:00:00Z"


def _req(**kw) -> DecisionRequest:
    base = dict(
        transition=Transition(
            transition_id="t-1",
            transition_type="CreateWorkRequest",
            proposed_by_principal_id="person-1",
            target_type="WorkRequest",
            operation="create",
        ),
        principal_active=True,
        required_authority="work_request.create",
        authority_evidence=(
            AuthorityEvidence(
                relationship_id="rel-1",
                relationship_type="RoleAssignment",
                principal_id="person-1",
                target_id="org-1",
                granted_authorities=("work_request.create",),
            ),
        ),
        evaluation_time=T,
    )
    base.update(kw)
    return DecisionRequest(**base)


def test_operator_view_has_exactly_the_four_required_fields() -> None:
    req = _req()
    view = operator_view(req, evaluate(req))
    assert set(view) == {"outcome", "reason", "material_finding", "next_action"}


def test_operator_view_names_the_material_limit_with_numbers() -> None:
    """An operator told 'budget exceeded' still has to go find the numbers."""
    req = _req(
        constraints=(
            BudgetCeiling(
                constraint_id="c-1", policy_version="pol-1@2", key="usd", limit=100.0
            ),
        ),
        cumulative_state={"usd": 120.5},
    )
    view = operator_view(req, evaluate(req))
    assert view["outcome"] == "Denied"
    assert "120.5" in view["material_finding"]
    assert "100" in view["material_finding"]
    assert "pol-1@2" in view["material_finding"]


def test_operator_next_action_is_actionable_not_a_shrug() -> None:
    req = _req(authority_evidence=())
    view = operator_view(req, evaluate(req))
    assert "work_request.create" in view["next_action"]
    assert "person-1" in view["next_action"]
    assert "contact an administrator" not in view["next_action"].lower()


def test_allowed_operator_view_says_no_action_needed() -> None:
    req = _req()
    view = operator_view(req, evaluate(req))
    assert view["outcome"] == "Allowed"
    assert view["material_finding"] is None
    assert "No action needed" in view["next_action"]


def test_approval_required_directs_to_the_approval() -> None:
    req = _req(
        constraints=(
            RequireApproval(
                constraint_id="c-4", policy_version="pol-1@1", approval_id="ap-7"
            ),
        )
    )
    view = operator_view(req, evaluate(req))
    assert view["outcome"] == "ApprovalRequired"
    assert "ap-7" in view["next_action"]


def test_proof_view_carries_every_required_section() -> None:
    req = _req()
    view = proof_view(req, evaluate(req))
    required = {
        "outcome",
        "reason_codes",
        "stages",
        "authorities_evaluated",
        "constraints_evaluated",
        "approval_findings",
        "revisions",
        "versions",
    }
    assert required <= set(view)


def test_proof_view_stages_are_in_normative_order() -> None:
    """Order is evidence. A proof that reorders stages is a different proof."""
    req = _req()
    view = proof_view(req, evaluate(req))
    assert [s["stage"] for s in view["stages"]] == list(STAGE_ORDER)


def test_proof_view_explains_why_an_authority_was_not_relied_upon() -> None:
    """An authority present but irrelevant must be distinguishable from one
    that was relied upon — otherwise the proof cannot answer 'I have a grant,
    why was I denied?'"""
    req = _req(
        required_authority="policy.override",
        authority_evidence=(
            AuthorityEvidence(
                relationship_id="rel-1",
                relationship_type="RoleAssignment",
                principal_id="person-1",
                target_id="org-1",
                granted_authorities=("work_request.create",),
            ),
        ),
    )
    view = proof_view(req, evaluate(req))
    entry = view["authorities_evaluated"][0]
    assert entry["matches_principal"] is True
    assert entry["grants_required_authority"] is False
    assert entry["was_a_candidate"] is False
    assert entry["relied_upon"] is False


def test_proof_view_reports_each_constraint_result(_=None) -> None:
    req = _req(
        constraints=(
            BudgetCeiling(
                constraint_id="c-ok", policy_version="p@1", key="usd", limit=100.0
            ),
            BudgetCeiling(
                constraint_id="c-bad", policy_version="p@1", key="tokens", limit=10.0
            ),
        ),
        cumulative_state={"usd": 50.0, "tokens": 99.0},
    )
    view = proof_view(req, evaluate(req))
    results = {c["constraint_id"]: c for c in view["constraints_evaluated"]}
    assert results["c-ok"]["result"] == "satisfied"
    assert results["c-bad"]["result"] == "failed"
    assert results["c-bad"]["observed"] == 99.0
    assert results["c-bad"]["limit"] == 10.0


def test_proof_view_records_versions_for_replay() -> None:
    req = _req()
    decision = evaluate(req)
    view = proof_view(req, decision)
    assert view["versions"]["kernel_version"] == decision.kernel_version
    assert view["versions"]["conformance_spec_version"] == "1"


def test_explanation_is_derived_not_stored() -> None:
    """Rewording the projection changes no evidence.

    The canonical Decision must be byte-identical regardless of what the
    explanation says about it.
    """
    from connect_governance_kernel import canonical_json

    req = _req(authority_evidence=())
    decision = evaluate(req)
    before = canonical_json(decision)

    both = explain(req, decision)
    assert both["operator"]["reason"]
    assert both["proof"]["reason_codes"]

    assert canonical_json(decision) == before
    # No prose from the projection leaks into the canonical record.
    assert "has not been granted" not in before


def test_projection_covers_every_reason_code() -> None:
    """A reason code with no plain-language sentence would surface a raw wire
    value to a non-technical operator."""
    from connect_governance.explanation import _REASON_PROSE
    from connect_governance_kernel import ReasonCode

    missing = {c for c in ReasonCode} - set(_REASON_PROSE)
    assert not missing, f"reason codes with no operator prose: {sorted(missing)}"
