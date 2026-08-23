"""The curated marketplace: listings and governed activation (R8, ADR-055).

The claims under test: an operator holding ``provider.list`` writes a curated
listing with its classification and evidence basis stored canonically; an
operator holding ``provider.activate`` activates a listed provider with a
replayable Allowed Decision Record linked from the activation; an
unauthorized activation is refused and *nothing* persists; and the ADR-041
evidence rule is fail-closed — an enforcing listing without evidence is
refused before any Decision is even evaluated, while a monitor-only listing
needs none.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from connect_governance.db.models import (
    AuthorityRelationship,
    DecisionRecord,
    ProviderActivation,
    ProviderListing,
)
from connect_governance.db.session import create_all, make_engine, session_factory
from connect_governance.decisions import replay
from connect_governance.genesis import GenesisRequest, initialize_deployment
from connect_governance.providers import (
    ProviderActivationRefused,
    ProviderListingRefused,
    activate_provider,
    create_listing,
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
        # person-1 holds authority.grant from Genesis; in-fixture we record
        # the ordinary AuthorityRelationship rows such a grant would write,
        # giving the operator the provider-curation vocabulary (ADR-055).
        s.add(
            AuthorityRelationship(
                id="auth-operator",
                relationship_type="OperatorGrant",
                principal_id="person-1",
                target_id="org-1",
                granted_authorities=json.dumps(["provider.list", "provider.activate"]),
                effective_from=T,
                effective_until=None,
                revoked_at=None,
                recorded_at=T,
                provenance="auth-genesis",
            )
        )
        s.flush()
        yield s


def _list(session, principal="person-1", listing_id="lst-1", **kw):
    args = dict(
        listing_id=listing_id,
        provider_id="toolconnect",
        name="ToolConnect",
        metadata={
            "capabilities": ["tool.invoke"],
            "compatibility": {"redemption_contract": "1"},
            "version": "0.7.0",
        },
        enforcement_classification="enforcing",
        classification_evidence={"conformance_vectors": ["rv-001", "rv-002"]},
        listed_by_principal_id=principal,
        transition_id=f"t-list-{listing_id}",
        decision_record_id=f"dr-list-{listing_id}",
        recorded_at=T,
        correlation_id="corr-1",
    )
    args.update(kw)
    return create_listing(session, **args)


def _activate(session, principal="person-1", activation_id="act-1", **kw):
    args = dict(
        activation_id=activation_id,
        listing_id="lst-1",
        activated_by_principal_id=principal,
        transition_id=f"t-activate-{activation_id}",
        decision_record_id=f"dr-activate-{activation_id}",
        recorded_at=T,
        correlation_id="corr-1",
    )
    args.update(kw)
    return activate_provider(session, **args)


def test_authorized_listing_persists_with_canonical_metadata_and_evidence(session) -> None:
    row = _list(session, metadata={"b": 2, "a": 1})
    assert row.id == "lst-1"
    assert row.provider_id == "toolconnect"
    assert row.enforcement_classification == "enforcing"
    assert row.provenance == "t-list-lst-1"
    assert row.metadata_json == '{"a":1,"b":2}'
    assert json.loads(row.classification_evidence_json) == {
        "conformance_vectors": ["rv-001", "rv-002"]
    }

    record = session.get(DecisionRecord, "dr-list-lst-1")
    assert record is not None
    assert record.outcome == "Allowed"
    assert replay(session, "dr-list-lst-1").matched


def test_monitor_only_listing_needs_no_evidence(session) -> None:
    row = _list(
        session,
        enforcement_classification="monitor_only",
        classification_evidence={},
    )
    assert row.enforcement_classification == "monitor_only"
    assert row.classification_evidence_json == "{}"


def test_enforcing_listing_without_evidence_is_refused_before_evaluation(session) -> None:
    with pytest.raises(ProviderListingRefused):
        _list(session, classification_evidence={})
    session.rollback()

    assert session.scalars(select(ProviderListing)).all() == []
    # The evidence rule fired before evaluation: no Decision Record exists.
    assert session.scalars(select(DecisionRecord)).all() == []


def test_unauthorized_listing_is_refused_and_nothing_persists(session) -> None:
    # agent-1 is active but holds no provider.list authority.
    with pytest.raises(ProviderListingRefused):
        _list(session, principal="agent-1")
    session.rollback()

    assert session.scalars(select(ProviderListing)).all() == []
    assert session.scalars(select(DecisionRecord)).all() == []


def test_authorized_activation_links_listing_and_decision_record(session) -> None:
    _list(session)
    row = _activate(session)
    assert row.state == "active"
    assert row.listing_id == "lst-1"
    assert row.decision_record_id == "dr-activate-act-1"
    assert row.provenance == "t-activate-act-1"

    record = session.get(DecisionRecord, "dr-activate-act-1")
    assert record is not None
    assert record.outcome == "Allowed"
    assert record.correlation_id == "corr-1"
    assert replay(session, "dr-activate-act-1").matched


def test_unauthorized_activation_persists_nothing(session) -> None:
    _list(session)
    session.commit()  # the listing predates the refused activation
    # agent-1 holds no provider.activate authority.
    with pytest.raises(ProviderActivationRefused):
        _activate(session, principal="agent-1")
    session.rollback()

    assert session.scalars(select(ProviderActivation)).all() == []
    assert session.get(DecisionRecord, "dr-activate-act-1") is None
    # The listing survives — it predates the refused activation.
    assert session.get(ProviderListing, "lst-1") is not None


def test_activation_of_unknown_listing_is_refused(session) -> None:
    with pytest.raises(ProviderActivationRefused):
        _activate(session)
    session.rollback()

    assert session.scalars(select(ProviderActivation)).all() == []
    assert session.scalars(select(DecisionRecord)).all() == []


def test_listing_invents_nothing_all_instants_are_caller_supplied(session) -> None:
    later = "2026-08-10T10:00:00Z"
    _list(session, recorded_at=later)
    _activate(session, recorded_at=later)
    assert session.get(ProviderListing, "lst-1").recorded_at == later
    assert session.get(ProviderActivation, "act-1").recorded_at == later
    record = session.get(DecisionRecord, "dr-activate-act-1")
    assert record.evaluated_at == later
    assert record.recorded_at == later
