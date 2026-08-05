"""Work Request intake: Kernel-evaluated, fail-closed, fully recorded.

The claims under test: an authorized principal creates a Work Request with
its first revision and a replayable Allowed Decision Record; an unauthorized
or inactive principal is refused and *nothing* — not the Work Request, not
its revision, not the Decision Record — survives the transaction.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from connect_governance.db.models import (
    DecisionRecord,
    Person,
    WorkRequest,
    WorkRequestRevision,
)
from connect_governance.db.session import create_all, make_engine, session_factory
from connect_governance.decisions import replay
from connect_governance.genesis import GenesisRequest, initialize_deployment
from connect_governance.resolution import current_state_revision
from connect_governance.work_requests import (
    WorkRequestRefused,
    create_work_request,
)

T = "2026-08-10T09:30:00Z"


@pytest.fixture()
def session():
    engine = make_engine()
    create_all(engine)
    with session_factory(engine)() as s:
        initialize_deployment(
            s,
            GenesisRequest(
                deployment_root_fingerprint="SHA256:deadbeef",
                installer="installer",
                software_version="0.0.1",
                initial_policy_hash="sha256:p",
                initial_config_hash="sha256:c",
                organization_id="org-1",
                organization_name="Org",
                workspace_id="ws-1",
                workspace_name="WS",
                founding_person_id="person-1",
                founding_person_name="Founder",
                initial_agent_id="agent-1",
                initial_agent_name="Agent",
                authority_id="auth-genesis",
                recorded_at=T,
            ),
        )
        yield s


def _create(session, principal="person-1", work_request_id="wr-1", **kw):
    args = dict(
        work_request_id=work_request_id,
        owner_organization_id="org-1",
        workspace_id="ws-1",
        created_by_principal_id=principal,
        revision_id=f"rev-{work_request_id}-1",
        state_revision=f"sr-{work_request_id}-1",
        governance={"title": "Quarterly close", "scope": "finance"},
        granted_authorities=("work_request.create",),
        budget_ceiling_usd=5000.0,
        transition_id=f"t-create-{work_request_id}",
        decision_record_id=f"dr-create-{work_request_id}",
        recorded_at=T,
        correlation_id="corr-1",
    )
    args.update(kw)
    return create_work_request(session, **args)


def test_authorized_creation_persists_request_revision_and_decision(session) -> None:
    row = _create(session)
    assert row.id == "wr-1"
    assert row.provenance == "t-create-wr-1"

    revision = session.scalars(
        select(WorkRequestRevision).where(WorkRequestRevision.work_request_id == "wr-1")
    ).one()
    assert revision.revision_number == 1
    assert revision.supersedes_revision_id is None
    assert json.loads(revision.governance_json) == {
        "title": "Quarterly close",
        "scope": "finance",
    }
    assert current_state_revision(session, "wr-1") == "sr-wr-1-1"

    record = session.get(DecisionRecord, "dr-create-wr-1")
    assert record is not None
    assert record.outcome == "Allowed"
    assert record.work_request_id == "wr-1"
    assert record.correlation_id == "corr-1"
    # The intake Decision is ordinary evidence: it replays byte-for-byte.
    assert replay(session, "dr-create-wr-1").matched


def test_governance_json_is_stored_canonically(session) -> None:
    _create(session, governance={"b": 2, "a": 1})
    revision = session.scalars(
        select(WorkRequestRevision).where(WorkRequestRevision.work_request_id == "wr-1")
    ).one()
    assert revision.governance_json == '{"a":1,"b":2}'


def test_unauthorized_principal_is_refused_and_nothing_persists(session) -> None:
    # agent-1 is active but holds no work_request.create authority.
    with pytest.raises(WorkRequestRefused):
        _create(session, principal="agent-1")
    session.rollback()

    assert session.scalars(select(WorkRequest)).all() == []
    assert session.scalars(select(WorkRequestRevision)).all() == []
    assert session.scalars(select(DecisionRecord)).all() == []


def test_inactive_principal_is_refused_and_nothing_persists(session) -> None:
    person = session.get(Person, "person-1")
    person.active = False
    session.flush()

    with pytest.raises(WorkRequestRefused):
        _create(session)
    session.rollback()

    assert session.scalars(select(WorkRequest)).all() == []
    assert session.scalars(select(DecisionRecord)).all() == []


def test_intake_invents_nothing_all_instants_are_caller_supplied(session) -> None:
    later = "2026-08-10T10:00:00Z"
    _create(session, recorded_at=later)
    record = session.get(DecisionRecord, "dr-create-wr-1")
    assert record.evaluated_at == later
    assert record.recorded_at == later
    assert session.get(WorkRequest, "wr-1").recorded_at == later
