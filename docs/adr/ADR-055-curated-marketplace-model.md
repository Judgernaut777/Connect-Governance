# ADR-055: The curated marketplace model — operator-authored listings and governed provider activation

**Status:** Accepted
**Date:** 2026-08-10
**Deciders:** Architecture review
**Related:** RA v0.2 §8 (provider classification) and §9 (curated marketplace),
ADR-039 (monitor-only must never be presented as preventative), ADR-040 (no
self-publishing), ADR-041 (conformance evidence as prerequisite for enforcing),
ADR-042 (Genesis), ADR-054 (Work Request intake — the idiom this mirrors)

## Context

R8 builds the curated marketplace surface: enough to activate ToolConnect as
an enforcing provider and display its enforcement classification. Two
governance-side questions had no answer in any repo:

1. **Where does a provider listing live?** RA v0.2 §9 makes the marketplace a
   curated MVP — operator-authored listings, no self-publishing (ADR-040) —
   but no schema or write path existed.
2. **What kind of act is provider activation?** The ecosystem's own doctrine
   answers this: activation is a governed decision, so it must be a
   Kernel-evaluated Transition with a Decision Record, exactly like Work
   Request intake (ADR-054), not a raw row write.

The enforcement classification needed equal care. RA v0.2 §8 makes it a
DECLARED, attested property of the provider, and ADR-039 is absolute: a
monitor-only provider must never be presented as preventative. ADR-041 makes
conformance evidence a prerequisite for declaring `enforcing`.

## Decision

1. **Listings are operator-curated writes into Connect-Governance, kernel-
   evaluated like everything else.** `providers.create_listing(session, *,
   ...)` builds a `CreateProviderListing` Transition, evaluates it through
   the Kernel with `required_authority="provider.list"`, and persists the
   `ProviderListing` and its Decision Record in the caller's transaction —
   fail-closed on anything other than Allowed, exactly the
   `work_requests.py` idiom. `provider.list` is not one of the four founding
   authorities; it enters the authority vocabulary as an ordinary granted
   key, written through the existing `authority.grant` path. The authority
   vocabulary is deliberately open — the Kernel compares
   `required_authority in granted_authorities` over free-form strings and
   never enumerates the keys — so reserving a new key is a governance act
   (granting it), not a code change.
2. **Activation is a Kernel-evaluated Transition; the activation row links
   its evidence.** `providers.activate_provider(session, *, ...)` evaluates
   an `ActivateProvider` Transition with `required_authority=
   "provider.activate"` and persists a `ProviderActivation` naming both the
   listing and the `decision_record_id` that authorized it. The authority
   key `provider.deactivate` is **reserved** but unused in R8: the schema
   admits `disabled` and `revoked` states so history needs no migration
   later, but no write path produces them — the lifecycle is deferred.
3. **Classification is a declared property plus its stored evidence basis,
   fail-closed.** `ProviderListing.enforcement_classification` is
   CHECK-constrained to `("enforcing", "monitor_only")`; nothing else can be
   stored. A listing declaring `enforcing` with empty
   `classification_evidence` is refused **before any Kernel evaluation** —
   ADR-041 is a property of the write path, not a display convention, so a
   control plane reading the table can trust that every stored enforcing
   listing names its evidence (e.g. conformance-vector pass references).
   `monitor_only` carries no evidence requirement.
4. **Listings ride the Option-B read projection in R8.** The marketplace
   surface reads listings and activations from the governance database
   through the thin `queries.py` wrappers (`list_listings`,
   `activations_for_listing`, `active_activation`), the same documented
   Option-B exception R7 used for the audit-trail surfaces. Per-plane read
   APIs remain the migration path; this ADR does not change that.

### Explicitly not decided

* **OD-010 (entitlement / pricing).** No pricing, entitlement, revenue-share,
  or billing fields exist on either table. Adding them later is additive.
* **OD-011 (certification programs).** The `classification_evidence` payload
  can reference conformance evidence, but no certification program, badge, or
  expiry semantics are defined.

## Consequences

* The marketplace has exactly one listing write path and one activation write
  path, both governed: a control plane importing this library cannot list or
  activate a provider the Kernel denied without forking the library.
* Every stored `enforcing` classification carries a non-empty evidence basis;
  "unverified" never needs to be a stored state because an unverifiable
  enforcing claim cannot be written.
* Activation Decisions replay byte-for-byte like every other Decision, so the
  marketplace surface's "activated" badge is traversable back to immutable
  evidence.
* The deferred disable/revoke lifecycle means R8 cannot *remove* a provider
  from the active set through this library; that is deliberate scope, tracked
  under the reserved `provider.deactivate` key.
* ROADMAP R8 is **not** marked done by this change; that follows the
  cross-repo verification stage.
