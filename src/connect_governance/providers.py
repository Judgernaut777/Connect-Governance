"""The curated marketplace: operator-authored listings and governed activation.

The marketplace is a curated MVP (RA v0.2 §9, ADR-040, ADR-055): there is no
self-publishing path. A listing is written by an operator principal holding
``provider.list`` authority, and activating a listed provider is itself an
authorization event — evaluated by the Kernel like any other, exactly as Work
Request intake is (ADR-054). No state is written until the Kernel has rendered
an Allowed Decision, and that Decision is recorded with the full evidence.

Two properties are structural, not documented:

* **Classification is a declared, attested property.** A listing declares
  ``enforcing`` or ``monitor_only`` (RA v0.2 §8); the schema admits nothing
  else, and a monitor-only provider must never be presented as enforcing
  (ADR-039). The declaration is only as strong as its evidence basis, which
  is stored with the listing in canonical form.
* **Enforcing requires evidence, fail-closed** (ADR-041). A listing declaring
  ``enforcing`` with empty ``classification_evidence`` is refused before any
  Kernel evaluation — the conformance evidence is a prerequisite for the
  classification, not an annotation on it. ``monitor_only`` carries no such
  requirement.

Fail-closed: if the Kernel renders anything other than Allowed, these functions
raise and nothing they touched is persisted. Atomicity is the caller's
transaction: evaluate, record, and write inside one transaction, and the
refusal unwinds all of it.

Nothing here reads a clock. Every instant and every id is supplied by the
caller, so listing and activation are reproducible in tests and replayable
like every other governed act.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from sqlalchemy.orm import Session

from connect_governance_kernel import Transition, canonical_json

from .decisions import evaluate_and_record
from .db.models import ProviderActivation, ProviderListing
from .resolution import build_decision_request

#: The authority key an operator must hold to write a curated listing.
#: Not one of the founding authorities; it enters the vocabulary as an
#: ordinary granted key via ``authority.grant`` (ADR-055).
LIST_REQUIRED_AUTHORITY = "provider.list"

#: The single authority key provider activation requires (ADR-055). The
#: companion key ``provider.deactivate`` is reserved but unused in R8 — the
#: disable/revoke lifecycle is deferred.
REQUIRED_AUTHORITY = "provider.activate"


class ProviderListingRefused(Exception):
    """The listing was refused: the Kernel did not Allow it, or an
    ``enforcing`` classification was declared without evidence (ADR-041).

    Nothing is persisted: the caller's transaction rolls back the recorded
    Decision together with any partial state.
    """


class ProviderActivationRefused(Exception):
    """The Kernel did not Allow this provider activation.

    Nothing is persisted: the caller's transaction rolls back the recorded
    Decision together with any partial state.
    """


def create_listing(
    session: Session,
    *,
    listing_id: str,
    provider_id: str,
    name: str,
    metadata: Mapping[str, Any],
    enforcement_classification: str,
    classification_evidence: Mapping[str, Any] | Sequence[Any],
    listed_by_principal_id: str,
    transition_id: str,
    decision_record_id: str,
    recorded_at: str,
    correlation_id: str | None = None,
) -> ProviderListing:
    """Write a curated provider listing, if Allowed.

    Fail-closed on the ADR-041 evidence rule *before* evaluation: an
    ``enforcing`` classification with empty ``classification_evidence``
    raises :class:`ProviderListingRefused` and no Decision is even
    evaluated. Otherwise the Kernel evaluates a ``CreateProviderListing``
    Transition with ``required_authority="provider.list"`` at the
    caller-supplied ``recorded_at`` instant; the Decision Record is
    persisted with the full request and decision. On any outcome other than
    Allowed, raises :class:`ProviderListingRefused` — the listing and the
    Decision Record must not survive the caller's rollback.

    ``metadata`` (capability, compatibility, version — RA v0.2 §8) and
    ``classification_evidence`` (e.g. conformance-vector pass references)
    are stored in canonical form so the stored bytes are reproducible.
    """
    if enforcement_classification == "enforcing" and not classification_evidence:
        raise ProviderListingRefused(
            f"Provider listing {listing_id!r} declares 'enforcing' without "
            "classification evidence; conformance evidence is a prerequisite "
            "for an enforcing listing (ADR-041)"
        )
    request = build_decision_request(
        session,
        transition=Transition(
            transition_id=transition_id,
            transition_type="CreateProviderListing",
            proposed_by_principal_id=listed_by_principal_id,
            target_type="ProviderListing",
            target_id=listing_id,
            operation="create",
            claims={
                "listing_id": listing_id,
                "provider_id": provider_id,
                "enforcement_classification": enforcement_classification,
            },
        ),
        required_authority=LIST_REQUIRED_AUTHORITY,
        evaluation_time=recorded_at,
        correlation_id=correlation_id,
    )
    decision, _record = evaluate_and_record(
        session,
        record_id=decision_record_id,
        request=request,
        recorded_at=recorded_at,
    )
    if decision.outcome != "Allowed":
        raise ProviderListingRefused(
            f"Provider listing {listing_id!r} was not created: the Kernel "
            f"rendered {decision.outcome.value!r} for "
            f"{LIST_REQUIRED_AUTHORITY!r} (Decision Record {decision_record_id!r})"
        )

    row = ProviderListing(
        id=listing_id,
        provider_id=provider_id,
        name=name,
        metadata_json=canonical_json(metadata),
        enforcement_classification=enforcement_classification,
        classification_evidence_json=canonical_json(classification_evidence),
        recorded_at=recorded_at,
        provenance=transition_id,
    )
    session.add(row)
    session.flush()
    return row


def activate_provider(
    session: Session,
    *,
    activation_id: str,
    listing_id: str,
    activated_by_principal_id: str,
    transition_id: str,
    decision_record_id: str,
    recorded_at: str,
    correlation_id: str | None = None,
) -> ProviderActivation:
    """Activate a listed provider, if Allowed.

    The Kernel evaluates an ``ActivateProvider`` Transition with
    ``required_authority="provider.activate"`` at the caller-supplied
    ``recorded_at`` instant; the Decision Record is persisted with the full
    request and decision. On any outcome other than Allowed, raises
    :class:`ProviderActivationRefused` — the activation and the Decision
    Record must not survive the caller's rollback.

    The activation row names the listing it activates and the Decision
    Record that authorized it, so the marketplace surface can traverse from
    a displayed provider back to the exact evidence for its activation.
    R8 writes only ``state="active"``; disabling and revoking are deferred
    (ADR-055).
    """
    if session.get(ProviderListing, listing_id) is None:
        raise ProviderActivationRefused(
            f"no provider listing {listing_id!r}; only a curated listing can "
            "be activated (ADR-040)"
        )
    request = build_decision_request(
        session,
        transition=Transition(
            transition_id=transition_id,
            transition_type="ActivateProvider",
            proposed_by_principal_id=activated_by_principal_id,
            target_type="ProviderListing",
            target_id=listing_id,
            operation="activate",
            claims={"listing_id": listing_id, "activation_id": activation_id},
        ),
        required_authority=REQUIRED_AUTHORITY,
        evaluation_time=recorded_at,
        correlation_id=correlation_id,
    )
    decision, _record = evaluate_and_record(
        session,
        record_id=decision_record_id,
        request=request,
        recorded_at=recorded_at,
    )
    if decision.outcome != "Allowed":
        raise ProviderActivationRefused(
            f"Provider listing {listing_id!r} was not activated: the Kernel "
            f"rendered {decision.outcome.value!r} for "
            f"{REQUIRED_AUTHORITY!r} (Decision Record {decision_record_id!r})"
        )

    row = ProviderActivation(
        id=activation_id,
        listing_id=listing_id,
        decision_record_id=decision_record_id,
        state="active",
        recorded_at=recorded_at,
        provenance=transition_id,
    )
    session.add(row)
    session.flush()
    return row
