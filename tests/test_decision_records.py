"""Decision Records: complete structured evidence, and replayable.

The record must carry everything needed to reproduce the Decision later. The
test of that is not inspection but reconstruction: re-evaluate the stored
request and compare bytes.
"""

from __future__ import annotations

import json

import pytest

from connect_governance.db.models import DecisionRecord
from connect_governance.db.session import create_all, make_engine, session_factory
from connect_governance.decisions import (
    CONFORMANCE_SPEC_VERSION,
    evaluate_and_record,
    load_record,
    replay,
    replay_all,
)
from connect_governance.genesis import GenesisRequest, initialize_deployment
from connect_governance.resolution import build_decision_request
from connect_governance_kernel import Transition, canonical_json

T = "2026-08-03T12:00:00Z"


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


def _request(session, principal="person-1", authority="work_request.create"):
    return build_decision_request(
        session,
        transition=Transition(
            transition_id="t-1",
            transition_type="CreateWorkRequest",
            proposed_by_principal_id=principal,
            target_type="WorkRequest",
            operation="create",
        ),
        required_authority=authority,
        evaluation_time=T,
        correlation_id="corr-1",
    )


def test_record_stores_the_complete_request_and_decision(session) -> None:
    request = _request(session)
    decision, row = evaluate_and_record(
        session, record_id="dr-1", request=request, recorded_at=T
    )

    assert row.outcome == decision.outcome.value
    assert row.kernel_version == decision.kernel_version
    assert row.conformance_spec_version == CONFORMANCE_SPEC_VERSION
    assert row.evaluated_at == T
    # The stored request is the exact input, not a summary of it.
    assert json.loads(row.request_json) == json.loads(canonical_json(request))


def test_stored_record_replays_byte_identically(session) -> None:
    evaluate_and_record(session, record_id="dr-1", request=_request(session), recorded_at=T)
    result = replay(session, "dr-1")
    assert result.matched
    assert result.stored_decision == result.replayed_decision


def test_replay_covers_denied_and_allowed_alike(session) -> None:
    evaluate_and_record(session, record_id="dr-allow", request=_request(session), recorded_at=T)
    evaluate_and_record(
        session,
        record_id="dr-deny",
        request=_request(session, authority="policy.override"),
        recorded_at=T,
    )
    results = replay_all(session)
    assert len(results) == 2
    assert all(r.matched for r in results)
    outcomes = {
        session.get(DecisionRecord, r.record_id).outcome for r in results
    }
    assert outcomes == {"Allowed", "Denied"}


def test_explanation_is_not_persisted(session) -> None:
    """Prose must never be the record.

    Storing rendered prose would tie a permanent record to the wording of the
    day it was written, and let an explanation drift from the evidence it
    claims to describe.
    """
    evaluate_and_record(session, record_id="dr-1", request=_request(session), recorded_at=T)
    row = session.get(DecisionRecord, "dr-1")
    columns = {c.name for c in DecisionRecord.__table__.columns}
    assert not {"explanation", "reason_text", "message", "prose"} & columns

    blob = f"{row.request_json}{row.decision_json}"
    # A sentence from the projection must not appear anywhere in the record.
    assert "does not start until later" not in blob
    assert "No action needed" not in blob


def test_record_rehydrates_into_structured_objects(session) -> None:
    original = _request(session)
    decision, _ = evaluate_and_record(
        session, record_id="dr-1", request=original, recorded_at=T
    )
    loaded_request, loaded_decision = load_record(session, "dr-1")
    assert canonical_json(loaded_request) == canonical_json(original)
    assert canonical_json(loaded_decision) == canonical_json(decision)


def test_replay_of_unknown_record_raises(session) -> None:
    with pytest.raises(KeyError):
        replay(session, "nope")


def test_decision_round_trips_from_its_own_canonical_form(session) -> None:
    """A stored Decision must rehydrate into the object that produced it.

    Regression: the Decision model was strict, so enum members serialized as
    plain strings could not be validated back. Records were writable but not
    loadable — replay tooling would have failed on real data while every
    in-memory test passed.
    """
    from connect_governance_kernel import Decision

    request = _request(session)
    decision, row = evaluate_and_record(
        session, record_id="dr-rt", request=request, recorded_at=T
    )
    rehydrated = Decision.model_validate(json.loads(row.decision_json))
    assert canonical_json(rehydrated) == canonical_json(decision)
    assert rehydrated.outcome is decision.outcome
    assert list(rehydrated.reason_codes) == list(decision.reason_codes)
