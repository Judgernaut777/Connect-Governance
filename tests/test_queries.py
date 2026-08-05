"""The single-identifier read surface: traversal by any linkage id.

Seeds one full governance chain — intake Decision, later Decision, issued
grant — and checks that each of the four queries returns exactly the records
naming the asked-for id, deterministically ordered.
"""

from __future__ import annotations

import pytest

from connect_governance.db.session import create_all, make_engine, session_factory
from connect_governance.genesis import GenesisRequest, initialize_deployment
from connect_governance.grants import issue_grant
from connect_governance.queries import (
    decisions_for_work_request,
    grants_by_decision_record,
    grants_for_work_request,
    records_for_correlation,
)
from connect_governance.work_requests import create_work_request

T = "2026-08-10T09:30:00Z"

PRIVATE_KEY_PEM = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MC4CAQAwBQYDK2VwBCIEIDkN5Il+uD9CLnuM+KTlqM+bKDnJql49TksMqQZ8Z3Kh\n"
    "-----END PRIVATE KEY-----\n"
)
KEY_ID = "ed25519:f294dcbe2bea2831af6df47eaf039ec5b7b223644dd1689f63be2d90bb5d800a"


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
        _seed(s)
        yield s


def _seed(s) -> None:
    for n in (1, 2):
        create_work_request(
            s,
            work_request_id=f"wr-{n}",
            owner_organization_id="org-1",
            workspace_id="ws-1",
            created_by_principal_id="person-1",
            revision_id=f"rev-wr-{n}-1",
            state_revision=f"sr-wr-{n}-1",
            governance={"title": f"WR {n}"},
            granted_authorities=("work_request.create",),
            budget_ceiling_usd=None,
            transition_id=f"t-create-wr-{n}",
            decision_record_id=f"dr-create-wr-{n}",
            recorded_at=T,
            correlation_id="corr-shared",
        )
    issue_grant(
        s,
        decision_record_id="dr-create-wr-1",
        grant_id="g-1",
        private_key_pem=PRIVATE_KEY_PEM,
        issuer_key_id=KEY_ID,
        work_request_id="wr-1",
        work_request_revision="sr-wr-1-1",
        requesting_principal_id="agent-1",
        organization_id="org-1",
        workspace_id="ws-1",
        provider_id="toolconnect",
        permitted_operations=("tool.invoke",),
        issued_at=T,
        not_after="2026-08-11T00:00:00Z",
        correlation_id="corr-shared",
    )


def test_grants_for_work_request_returns_only_its_grants(session) -> None:
    grants = grants_for_work_request(session, "wr-1")
    assert [g.id for g in grants] == ["g-1"]
    assert grants[0].decision_record_id == "dr-create-wr-1"
    assert grants_for_work_request(session, "wr-2") == []


def test_decisions_for_work_request_returns_intake_decision(session) -> None:
    decisions = decisions_for_work_request(session, "wr-1")
    assert [d.id for d in decisions] == ["dr-create-wr-1"]
    assert decisions[0].outcome == "Allowed"


def test_grants_by_decision_record(session) -> None:
    grants = grants_by_decision_record(session, "dr-create-wr-1")
    assert [g.id for g in grants] == ["g-1"]
    assert grants_by_decision_record(session, "dr-create-wr-2") == []


def test_records_for_correlation_joins_both_record_kinds(session) -> None:
    decisions, grants = records_for_correlation(session, "corr-shared")
    assert [d.id for d in decisions] == ["dr-create-wr-1", "dr-create-wr-2"]
    assert [g.id for g in grants] == ["g-1"]


def test_unknown_ids_return_empty(session) -> None:
    assert grants_for_work_request(session, "wr-nope") == []
    assert decisions_for_work_request(session, "wr-nope") == []
    assert grants_by_decision_record(session, "dr-nope") == []
    assert records_for_correlation(session, "corr-nope") == ([], [])
