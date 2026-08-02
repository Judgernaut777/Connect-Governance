"""Determinism and replay.

The Kernel's central claim is that an identical input yields an identical
Decision — which is what makes a Decision Record replayable years later, and
what makes an alternative implementation checkable. These tests attack that
claim rather than illustrate it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from connect_governance_kernel import DecisionRequest, canonical_json, evaluate

VECTOR_DIR = Path(__file__).resolve().parents[1] / "conformance" / "vectors"
VECTORS = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(VECTOR_DIR.glob("*.json"))]


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["vector_id"])
def test_repeated_evaluation_is_byte_identical(vector: dict) -> None:
    """Replay: the same request evaluated many times yields identical bytes."""
    request = DecisionRequest.model_validate(vector["input"])
    first = canonical_json(evaluate(request))
    for _ in range(25):
        assert canonical_json(evaluate(request)) == first


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["vector_id"])
def test_input_key_order_does_not_affect_the_decision(vector: dict) -> None:
    """JSON object key order is not semantic.

    Two callers serializing the same facts in different key orders must receive
    the same Decision, or the vectors would be testing a serializer rather than
    a Kernel.
    """
    payload = vector["input"]
    reversed_payload = {k: payload[k] for k in reversed(list(payload.keys()))}
    assert canonical_json(evaluate(DecisionRequest.model_validate(payload))) == canonical_json(
        evaluate(DecisionRequest.model_validate(reversed_payload))
    )


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["vector_id"])
def test_evaluation_does_not_mutate_its_input(vector: dict) -> None:
    """A Kernel that edited its inputs could not be replayed against them."""
    payload = vector["input"]
    before = json.dumps(payload, sort_keys=True)
    request = DecisionRequest.model_validate(payload)
    evaluate(request)
    assert json.dumps(payload, sort_keys=True) == before


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["vector_id"])
def test_evaluated_at_echoes_the_supplied_time_exactly(vector: dict) -> None:
    """The Kernel reports the time it was given, never a time it observed."""
    request = DecisionRequest.model_validate(vector["input"])
    assert evaluate(request).evaluated_at == request.evaluation_time


@settings(max_examples=200, deadline=None)
@given(
    active=st.booleans(),
    has_authority=st.booleans(),
    spend=st.floats(min_value=0, max_value=200, allow_nan=False, allow_infinity=False),
    limit=st.floats(min_value=0, max_value=200, allow_nan=False, allow_infinity=False),
)
def test_property_denial_requires_a_failed_condition(
    active: bool, has_authority: bool, spend: float, limit: float
) -> None:
    """Invariants that must hold for every input, not just the vectors:

    a Denied outcome always names at least one failed condition, an Allowed
    outcome names none and requires no approval, and no outcome is ever
    returned without at least one reason code. An unexplained Decision would
    violate ADR-023 regardless of which inputs produced it.
    """
    request = DecisionRequest.model_validate(
        {
            "transition": {
                "transition_id": "t-prop",
                "transition_type": "CreateWorkRequest",
                "proposed_by_principal_id": "person-1",
                "target_type": "WorkRequest",
                "target_id": None,
                "operation": "create",
                "claims": {},
                "expected_state_revision": None,
            },
            "principal_active": active,
            "required_authority": "work_request.create",
            "current_state_revision": None,
            "authority_evidence": (
                [
                    {
                        "relationship_id": "rel-1",
                        "relationship_type": "RoleAssignment",
                        "principal_id": "person-1",
                        "target_id": "workspace-1",
                        "granted_authorities": ["work_request.create"],
                        "effective_from": None,
                        "effective_until": None,
                        "revoked_at": None,
                    }
                ]
                if has_authority
                else []
            ),
            "policy_versions": [],
            "constraints": [
                {
                    "kind": "budget_ceiling",
                    "constraint_id": "c-1",
                    "policy_version": "pol@1",
                    "key": "usd",
                    "limit": limit,
                }
            ],
            "classifications": {},
            "cumulative_state": {"usd": spend},
            "delegation": None,
            "evaluation_time": "2026-08-03T12:00:00Z",
            "correlation_id": None,
        }
    )
    decision = evaluate(request)

    assert decision.reason_codes, "every Decision must be explainable"
    if decision.outcome == "Denied":
        assert decision.failed_conditions
    if decision.outcome == "Allowed":
        assert not decision.failed_conditions
        assert not decision.required_approvals
