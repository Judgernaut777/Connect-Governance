"""The Kernel's data contract holds its stated properties.

These are scaffold-level assertions on shape, not on evaluation logic — the
evaluator arrives in R1. What is checked here is what the contract *promises*:
inputs are frozen, strict, and closed; time is an explicit field; and the
Decision carries structured evidence rather than a bare outcome.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from connect_governance_kernel.types import (
    Decision,
    DecisionRequest,
    Outcome,
    ReasonCode,
    Transition,
)


def _transition() -> Transition:
    return Transition(
        transition_id="t-1",
        transition_type="CreateWorkRequest",
        proposed_by_principal_id="person-1",
        target_type="WorkRequest",
        operation="create",
    )


def _request() -> DecisionRequest:
    return DecisionRequest(
        transition=_transition(),
        principal_active=True,
        evaluation_time="2026-08-03T12:00:00Z",
    )


def test_evaluation_time_is_a_required_explicit_input() -> None:
    """The Kernel never reads a clock; the caller must supply the time."""
    with pytest.raises(ValidationError):
        DecisionRequest(transition=_transition(), principal_active=True)  # type: ignore[call-arg]


def test_request_is_frozen() -> None:
    req = _request()
    with pytest.raises(ValidationError):
        req.principal_active = False  # type: ignore[misc]


def test_request_rejects_unknown_fields() -> None:
    """A Kernel that silently ignores an unrecognized input cannot claim its
    Decision was evaluated against the inputs the caller believed it sent."""
    with pytest.raises(ValidationError):
        DecisionRequest(
            transition=_transition(),
            principal_active=True,
            evaluation_time="2026-08-03T12:00:00Z",
            surprise_field="unexpected",  # type: ignore[call-arg]
        )


def test_decision_carries_structured_evidence_not_a_bare_outcome() -> None:
    d = Decision(
        outcome=Outcome.DENIED,
        reason_codes=[ReasonCode.NO_EXPLICIT_AUTHORITY],
        transition_id="t-1",
        kernel_version="0.0.1",
        evaluated_at="2026-08-03T12:00:00Z",
        failed_conditions=["authority.explicit_required"],
    )
    assert d.reason_codes and d.failed_conditions
    assert d.outcome is Outcome.DENIED


def test_reason_codes_are_stable_wire_values() -> None:
    """Reason codes are a versioned machine-readable contract, not prose."""
    assert ReasonCode.NO_EXPLICIT_AUTHORITY == "authority.none_explicit"
    assert ReasonCode.PERMITTED == "permitted"
