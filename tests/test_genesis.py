"""Genesis: a distinct, once-only trust root that leaks nothing into evaluation.

The property under test is not merely "Genesis runs". It is that after Genesis
runs, **nothing about evaluation is different** — the founding authority is an
ordinary row, and the Kernel cannot tell it apart from any other. A bootstrap
that stayed special would be a permanent unexplainable exception inside a system
whose entire claim is that every Decision is explainable.
"""

from __future__ import annotations

import json

import pytest

from connect_governance.db.session import create_all, make_engine, session_factory
from connect_governance.genesis import (
    FOUNDING_AUTHORITIES,
    GENESIS_PROVENANCE,
    GenesisRefused,
    GenesisRequest,
    genesis_completed,
    initialize_deployment,
)
from connect_governance.db.models import (
    AuthorityRelationship,
    GenesisRecord,
    Organization,
)
from connect_governance_kernel import Transition

T = "2026-08-03T12:00:00Z"


def _request(**kw) -> GenesisRequest:
    base = dict(
        deployment_root_fingerprint="SHA256:deadbeef",
        installer="matthew.judge",
        software_version="0.0.1",
        initial_policy_hash="sha256:policy",
        initial_config_hash="sha256:config",
        organization_id="org-1",
        organization_name="Example Org",
        workspace_id="ws-1",
        workspace_name="Default Workspace",
        founding_person_id="person-1",
        founding_person_name="Founder",
        initial_agent_id="agent-1",
        initial_agent_name="First Agent",
        authority_id="auth-genesis",
        recorded_at=T,
    )
    base.update(kw)
    return GenesisRequest(**base)


@pytest.fixture()
def session():
    engine = make_engine()
    create_all(engine)
    with session_factory(engine)() as s:
        yield s


def test_genesis_creates_the_trust_root_and_records_provenance(session) -> None:
    result = initialize_deployment(session, _request())

    record = session.get(GenesisRecord, 1)
    assert record is not None
    # The external trust root is recorded, not invented: the origin of all
    # subsequent authority must be auditable rather than anonymous.
    assert record.deployment_root_fingerprint == "SHA256:deadbeef"
    assert record.installer == "matthew.judge"
    assert record.software_version == "0.0.1"
    assert record.initial_policy_hash == "sha256:policy"
    assert record.initial_config_hash == "sha256:config"
    assert record.initial_authority_id == result.authority_id

    org = session.get(Organization, "org-1")
    assert org is not None and org.provenance == GENESIS_PROVENANCE


def test_genesis_refuses_a_second_run(session) -> None:
    initialize_deployment(session, _request())
    assert genesis_completed(session)
    with pytest.raises(GenesisRefused):
        initialize_deployment(session, _request(organization_id="org-2"))


def test_genesis_refuses_when_state_already_exists(session) -> None:
    """A deployment with entities but no Genesis record is in an unexplained
    state; initializing a trust root into it would bless whatever is there."""
    session.add(
        Organization(
            id="org-preexisting", name="Squatter", recorded_at=T, provenance="unknown"
        )
    )
    session.flush()
    with pytest.raises(GenesisRefused):
        initialize_deployment(session, _request())


def test_genesis_refusal_is_not_silently_absorbed(session) -> None:
    """A second Genesis attempt raises rather than returning success.

    Idempotent-success would hide a serious operational event: something tried
    to re-root a live deployment.
    """
    initialize_deployment(session, _request())
    with pytest.raises(GenesisRefused):
        initialize_deployment(session, _request())


def test_founding_authority_is_an_ordinary_row(session) -> None:
    """The bootstrap grant carries no marker evaluation could branch on."""
    initialize_deployment(session, _request())
    row = session.get(AuthorityRelationship, "auth-genesis")
    assert row is not None
    assert row.principal_id == "person-1"
    assert set(json.loads(row.granted_authorities)) == set(FOUNDING_AUTHORITIES)
    # provenance exists for audit only; nothing in evaluation reads it.
    assert row.provenance == GENESIS_PROVENANCE
    assert row.revoked_at is None


def test_founding_authority_is_narrow_not_superuser(session) -> None:
    """Genesis grants enough to govern the first work, not everything forever."""
    initialize_deployment(session, _request())
    granted = set(FOUNDING_AUTHORITIES)
    assert "work_request.create" in granted
    for never in ("*", "admin.all", "authority.bypass", "policy.override"):
        assert never not in granted


def test_kernel_never_sees_genesis_provenance(session) -> None:
    """Resolution passes no provenance to the Kernel at all.

    If bootstrap were ever going to leak into evaluation, this is where it would
    happen — the resolver deciding to treat a genesis row differently.
    """
    from connect_governance_kernel import canonical_json, evaluate
    from connect_governance.resolution import build_decision_request, resolve_authority_evidence

    initialize_deployment(session, _request())
    evidence = resolve_authority_evidence(session, "person-1")
    assert len(evidence) == 1

    # The provenance column is never carried into Kernel input at all.
    assert "provenance" not in evidence[0].model_dump()

    # The descriptive labels that DO cross the boundary (relationship_id,
    # relationship_type) must carry no evaluative weight. Renaming the type
    # away from "GenesisGrant" must change nothing, which proves the Kernel
    # cannot be branching on it even though it can see it.
    transition = Transition(
        transition_id="t-1",
        transition_type="CreateWorkRequest",
        proposed_by_principal_id="person-1",
        target_type="WorkRequest",
        operation="create",
    )
    before = canonical_json(
        evaluate(
            build_decision_request(
                session,
                transition=transition,
                required_authority="work_request.create",
                evaluation_time=T,
            )
        )
    )

    row = session.get(AuthorityRelationship, "auth-genesis")
    row.relationship_type = "RoleAssignment"
    session.flush()

    after = canonical_json(
        evaluate(
            build_decision_request(
                session,
                transition=transition,
                required_authority="work_request.create",
                evaluation_time=T,
            )
        )
    )
    assert before == after, "relationship_type must carry no evaluative weight"


def test_genesis_authority_evaluates_identically_to_a_normal_grant(session) -> None:
    """The decisive test: swap the genesis grant for an ordinary one and the
    Decision is byte-identical apart from the relationship id."""
    from connect_governance_kernel import Transition, canonical_json, evaluate
    from connect_governance.resolution import build_decision_request

    initialize_deployment(session, _request())

    transition = Transition(
        transition_id="t-1",
        transition_type="CreateWorkRequest",
        proposed_by_principal_id="person-1",
        target_type="WorkRequest",
        operation="create",
    )
    genesis_decision = evaluate(
        build_decision_request(
            session,
            transition=transition,
            required_authority="work_request.create",
            evaluation_time=T,
        )
    )
    assert genesis_decision.outcome == "Allowed"
    assert list(genesis_decision.resolved_authorities) == ["auth-genesis"]

    # Now an ordinary grant to a different principal, identical in substance.
    session.add(
        AuthorityRelationship(
            id="auth-ordinary",
            relationship_type="RoleAssignment",
            principal_id="person-2",
            target_id="org-1",
            granted_authorities=json.dumps(list(FOUNDING_AUTHORITIES)),
            effective_from=T,
            effective_until=None,
            revoked_at=None,
            recorded_at=T,
            provenance="t-setup",
        )
    )
    from connect_governance.db.models import Person

    session.add(
        Person(id="person-2", display_name="Ordinary", active=True, recorded_at=T,
               provenance="t-setup")
    )
    session.flush()

    ordinary_decision = evaluate(
        build_decision_request(
            session,
            transition=transition.model_copy(update={"proposed_by_principal_id": "person-2"}),
            required_authority="work_request.create",
            evaluation_time=T,
        )
    )

    a = json.loads(canonical_json(genesis_decision))
    b = json.loads(canonical_json(ordinary_decision))
    a.pop("resolved_authorities")
    b.pop("resolved_authorities")
    assert a == b, "a genesis-derived authority must evaluate like any other"
