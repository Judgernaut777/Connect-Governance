"""The single-identifier read surface (R7, EXECUTION_RECORD.md §5).

The linked audit trail is traversable in both directions by id: given any of
``work_request_id``, ``decision_record_id``, ``grant_id``, or
``correlation_id``, these functions return the records naming the others.
Every column read here was indexed when the linkage ids landed (R3/R4/R6);
this module adds no schema and no decisions — it is a thin, deterministic
read layer over evidence that already exists.

Ordering is by primary key so results are a function of the data, not of
database iteration order. The human-readable surface (the Decision and its
explanation) is built on read from these records via
:mod:`connect_governance.explanation` — nothing rendered is stored.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.models import DecisionRecord, ExecutionGrantRecord


def grants_for_work_request(
    session: Session, work_request_id: str
) -> list[ExecutionGrantRecord]:
    """Every execution grant issued under this Work Request."""
    return list(
        session.scalars(
            select(ExecutionGrantRecord)
            .where(ExecutionGrantRecord.work_request_id == work_request_id)
            .order_by(ExecutionGrantRecord.id)
        ).all()
    )


def decisions_for_work_request(
    session: Session, work_request_id: str
) -> list[DecisionRecord]:
    """Every Decision Record — intake and later — naming this Work Request."""
    return list(
        session.scalars(
            select(DecisionRecord)
            .where(DecisionRecord.work_request_id == work_request_id)
            .order_by(DecisionRecord.id)
        ).all()
    )


def grants_by_decision_record(
    session: Session, decision_record_id: str
) -> list[ExecutionGrantRecord]:
    """Every grant issued from this Decision Record (R3/R4 linkage)."""
    return list(
        session.scalars(
            select(ExecutionGrantRecord)
            .where(ExecutionGrantRecord.decision_record_id == decision_record_id)
            .order_by(ExecutionGrantRecord.id)
        ).all()
    )


def records_for_correlation(
    session: Session, correlation_id: str
) -> tuple[list[DecisionRecord], list[ExecutionGrantRecord]]:
    """Both record kinds sharing one correlation id (ADR-037).

    Returns ``(decision_records, execution_grant_records)``, each ordered by
    primary key, so a caller joining across planes starts from the governance
    half of the trail without further lookups.
    """
    decisions = list(
        session.scalars(
            select(DecisionRecord)
            .where(DecisionRecord.correlation_id == correlation_id)
            .order_by(DecisionRecord.id)
        ).all()
    )
    grants = list(
        session.scalars(
            select(ExecutionGrantRecord)
            .where(ExecutionGrantRecord.correlation_id == correlation_id)
            .order_by(ExecutionGrantRecord.id)
        ).all()
    )
    return decisions, grants
