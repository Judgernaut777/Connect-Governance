"""Decision Records: persist the complete structured evidence, and replay it.

Every evaluation produces a durable record (ADR-024). The record stores the
**exact** request and the **exact** decision in canonical form, which is what
makes replay possible without reconstructing historical state — re-evaluate the
stored request and compare bytes.

What is deliberately *not* stored: the human-readable explanation. That is a
projection built on read (see :mod:`connect_governance.explanation`). Storing
rendered prose would tie the permanent record to the wording of the day it was
written, and would let an explanation drift away from the evidence it claims to
describe.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from connect_governance_kernel import (
    Decision,
    DecisionRequest,
    canonical_json,
    evaluate,
)

from .db.models import DecisionRecord

#: The conformance specification version this deployment evaluates against.
#: Stored on every record so a replay can tell "the Kernel changed" from "the
#: specification changed" — different problems with different remedies.
CONFORMANCE_SPEC_VERSION = "1"


@dataclass(frozen=True)
class ReplayResult:
    record_id: str
    matched: bool
    stored_decision: dict
    replayed_decision: dict


def record_decision(
    session: Session,
    *,
    record_id: str,
    request: DecisionRequest,
    decision: Decision,
    recorded_at: str,
    work_request_id: str | None = None,
) -> DecisionRecord:
    """Persist one Decision and the exact input that produced it."""
    row = DecisionRecord(
        id=record_id,
        transition_id=decision.transition_id,
        outcome=decision.outcome.value,
        request_json=canonical_json(request),
        decision_json=canonical_json(decision),
        kernel_version=decision.kernel_version,
        conformance_spec_version=CONFORMANCE_SPEC_VERSION,
        evaluated_at=decision.evaluated_at,
        recorded_at=recorded_at,
        correlation_id=decision.correlation_id,
        work_request_id=work_request_id,
        work_request_revision=request.current_state_revision,
    )
    session.add(row)
    session.flush()
    return row


def evaluate_and_record(
    session: Session,
    *,
    record_id: str,
    request: DecisionRequest,
    recorded_at: str,
    work_request_id: str | None = None,
) -> tuple[Decision, DecisionRecord]:
    """Evaluate a request and persist the result in one step."""
    decision = evaluate(request)
    row = record_decision(
        session,
        record_id=record_id,
        request=request,
        decision=decision,
        recorded_at=recorded_at,
        work_request_id=work_request_id,
    )
    return decision, row


def replay(session: Session, record_id: str) -> ReplayResult:
    """Re-evaluate a stored Decision Record and compare byte-for-byte.

    A mismatch is a real finding, and the record tells you which kind: if
    ``kernel_version`` differs from the running Kernel, behaviour changed
    between versions; if it matches, the current Kernel is nondeterministic and
    the determinism claim is false.
    """
    row = session.get(DecisionRecord, record_id)
    if row is None:
        raise KeyError(f"no Decision Record {record_id!r}")

    request = DecisionRequest.model_validate(json.loads(row.request_json))
    replayed = canonical_json(evaluate(request))
    return ReplayResult(
        record_id=record_id,
        matched=(replayed == row.decision_json),
        stored_decision=json.loads(row.decision_json),
        replayed_decision=json.loads(replayed),
    )


def replay_all(session: Session) -> list[ReplayResult]:
    """Replay every stored Decision Record. Used as an integrity sweep."""
    ids = session.scalars(select(DecisionRecord.id).order_by(DecisionRecord.id)).all()
    return [replay(session, rid) for rid in ids]


def load_record(session: Session, record_id: str) -> tuple[DecisionRequest, Decision]:
    """Rehydrate the structured request and decision from a stored record."""
    row = session.get(DecisionRecord, record_id)
    if row is None:
        raise KeyError(f"no Decision Record {record_id!r}")
    return (
        DecisionRequest.model_validate(json.loads(row.request_json)),
        Decision.model_validate(json.loads(row.decision_json)),
    )
