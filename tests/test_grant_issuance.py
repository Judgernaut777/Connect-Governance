"""Grant issuance: only an Allowed Decision can mint a grant, and it persists.

The load-bearing rule of R4 is not the signature — it is that a grant exists
*only* because a replayable Decision Record said Allowed. Issuance against
anything else is an authorization invented outside the Kernel.
"""

from __future__ import annotations

import json

import pytest

from connect_governance.db.models import ExecutionGrantRecord
from connect_governance.db.session import create_all, make_engine, session_factory
from connect_governance.decisions import evaluate_and_record
from connect_governance.genesis import GenesisRequest, initialize_deployment
from connect_governance.grants import (
    GrantIssuanceRefused,
    issue_grant,
    load_grant,
)
from connect_governance.resolution import build_decision_request
from connect_governance_grants import public_key_id, verify_grant
from connect_governance_kernel import Transition, canonical_json

T = "2026-08-03T12:00:00Z"

PRIVATE_KEY_PEM = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MC4CAQAwBQYDK2VwBCIEIDkN5Il+uD9CLnuM+KTlqM+bKDnJql49TksMqQZ8Z3Kh\n"
    "-----END PRIVATE KEY-----\n"
)
PUBLIC_KEY_PEM = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEA/XluIVKX4rL4Za5ar1AYWE26XHAjLGGYAoycsyl+/m0=\n"
    "-----END PUBLIC KEY-----\n"
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
        yield s


def _record(session, record_id: str, authority="work_request.create"):
    request = build_decision_request(
        session,
        transition=Transition(
            transition_id=f"t-{record_id}",
            transition_type="CreateWorkRequest",
            proposed_by_principal_id="person-1",
            target_type="WorkRequest",
            operation="create",
        ),
        required_authority=authority,
        evaluation_time=T,
        correlation_id="corr-1",
    )
    return evaluate_and_record(
        session, record_id=record_id, request=request, recorded_at=T
    )


def _issue(session, record_id="dr-allow"):
    return issue_grant(
        session,
        decision_record_id=record_id,
        grant_id="g-1",
        private_key_pem=PRIVATE_KEY_PEM,
        issuer_key_id=KEY_ID,
        work_request_id="wr-1",
        work_request_revision="rev-1",
        requesting_principal_id="agent-1",
        organization_id="org-1",
        workspace_id="ws-1",
        provider_id="toolconnect",
        permitted_operations=("tool.invoke",),
        issued_at=T,
        not_after="2026-08-04T00:00:00Z",
    )


def test_issuance_from_an_allowed_decision_succeeds(session) -> None:
    _record(session, "dr-allow")
    grant = _issue(session)
    assert grant.payload.decision_record_id == "dr-allow"
    assert grant.payload.issuer_key_id == KEY_ID
    assert verify_grant(grant, PUBLIC_KEY_PEM, at=T).valid


def test_issuance_from_a_denied_decision_is_refused(session) -> None:
    _record(session, "dr-deny", authority="policy.override")
    with pytest.raises(GrantIssuanceRefused):
        _issue(session, record_id="dr-deny")


def test_issuance_from_a_missing_record_is_refused(session) -> None:
    with pytest.raises(GrantIssuanceRefused):
        _issue(session, record_id="dr-nope")


def test_issued_grant_is_persisted_and_round_trips(session) -> None:
    _record(session, "dr-allow")
    grant = _issue(session)
    row = session.get(ExecutionGrantRecord, "g-1")
    assert row is not None
    assert row.decision_record_id == "dr-allow"
    assert row.issuer_key_id == KEY_ID
    assert row.correlation_id == "corr-1"

    loaded = load_grant(session, "g-1")
    assert canonical_json(loaded) == canonical_json(grant)
    # The stored artifact verifies as-is: no re-serialization trust needed.
    assert verify_grant(
        loaded, PUBLIC_KEY_PEM, at="2026-08-03T18:00:00Z"
    ).valid


def test_grant_inherits_policy_versions_and_kernel_version(session) -> None:
    """The grant names the exact versions the Decision was evaluated under."""
    _record(session, "dr-allow")
    grant = _issue(session)
    assert grant.payload.kernel_version == "0.0.1"
    assert list(grant.payload.policy_versions) == []


def test_grant_correlation_defaults_to_the_decisions(session) -> None:
    """One identifier must traverse record kinds (ADR-037)."""
    _record(session, "dr-allow")
    grant = _issue(session)
    assert grant.payload.correlation_id == "corr-1"


def test_issuance_is_reproducible(session) -> None:
    """Same facts + same key + same explicit time → byte-identical artifact."""
    _record(session, "dr-allow")
    grant = _issue(session)
    again = issue_grant(
        session,
        decision_record_id="dr-allow",
        grant_id="g-2",
        private_key_pem=PRIVATE_KEY_PEM,
        issuer_key_id=KEY_ID,
        work_request_id="wr-1",
        work_request_revision="rev-1",
        requesting_principal_id="agent-1",
        organization_id="org-1",
        workspace_id="ws-1",
        provider_id="toolconnect",
        permitted_operations=("tool.invoke",),
        issued_at=T,
        not_after="2026-08-04T00:00:00Z",
    )
    a = json.loads(canonical_json(grant))
    b = json.loads(canonical_json(again))
    a["payload"].pop("grant_id")
    b["payload"].pop("grant_id")
    # Only grant_id differs in the payload — and because grant_id is *signed*,
    # the signatures necessarily differ too. Determinism of an identical
    # payload is pinned in tests/test_grants.py.
    assert a["payload"] == b["payload"]
    assert grant.signature != again.signature


def test_load_of_unknown_grant_raises(session) -> None:
    with pytest.raises(KeyError):
        load_grant(session, "nope")


def test_public_key_id_helper_agrees_with_issuer(session) -> None:
    assert public_key_id(PUBLIC_KEY_PEM) == KEY_ID
