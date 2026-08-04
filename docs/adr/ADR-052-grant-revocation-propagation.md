# ADR-052: Grant revocation — short validity windows now, propagation deferred

**Status:** Accepted (resolves OD-009)
**Date:** 2026-08-04
**Deciders:** Architecture review
**Related:** ADR-038 (grants from Allowed Decisions), ADR-050 (Ed25519),
ADR-051 (issuer key custody; OD-009 opened there), REDEMPTION_CONTRACT.md §9

## Context

R4 gave Connect the ability to issue signed execution grants; R5 (the
redemption contract and ToolConnect's implementation of it) makes those grants
enforceable at the point of effect. ADR-051 deferred one question as **OD-009**:
once a grant is issued, how is it *revoked* before its natural expiry, and how
would a provider — which verifies grants **offline**, deliberately without
calling back into Connect — ever learn that a grant was revoked?

The tension is constitutional, not technical:

* Providers must not need a live connection to the governance plane to enforce.
  A decision point that requires a network call in a fail-closed path converts
  every network partition into a universal denial (or worse, a universal allow
  if someone "fails open" to avoid the outage).
* A grant is a signed, self-contained artifact. Nothing inside it can change
  after issuance without invalidating the signature. Revocation information
  therefore necessarily travels **outside** the artifact, on some channel every
  redeemer must consult — which reintroduces exactly the availability coupling
  the offline design exists to avoid.

The half-built versions of this are worse than either honest extreme: a
revocation feed providers "should" poll on an honor system is a control that
exists on paper and fails silently in production.

## Decision

For the first vertical slice, **the validity window is the revocation
mechanism**:

1. **Issuers MUST set short `not_after` windows.** Grant TTL is a governance
   decision made at issuance; the operational guidance for the slice is minutes,
   not days. The cost of "cannot revoke" is bounded by the window's length, and
   that bound is visible in the grant itself — an auditor can read the maximum
   exposure off the artifact.
2. **Redeemers enforce the window and nothing else** (REDEMPTION_CONTRACT.md §3):
   half-open, judged against a caller-supplied instant, never a clock in the
   verify path. There is no revocation check in the redemption path for the
   slice, and no pretend one.
3. **Revocation of the *issuer* is key rotation** (ADR-051): rotating the issuer
   key and updating provider trust roots invalidates every outstanding grant
   from the old key (`unknown_issuer` — fail closed). This is the only
   deployment-wide kill switch the slice has, and it is a real one.
4. **The revocation-list format is defined now; propagation is deferred to R7.**
   When revocation distribution lands, a revocation entry is a signed,
   canonical-JSON list:

   ```json
   {
     "revocation_list_format_version": "1",
     "issuer_key_id": "ed25519:...",
     "issued_at": "<RFC 3339>",
     "revoked_grant_ids": ["<grant_id>", "..."],
     "supersedes": "<prior list id or null>",
     "list_id": "<unique id>",
     "signature_scheme": "Ed25519",
     "signature": "<over the canonical encoding of the fields above, minus itself>"
   }
   ```

   Semantics reserved for R7: lists are issuer-signed, monotonic
   (`supersedes` chains them), and redeemers fail closed on a stale-or-missing
   list only for grants whose windows overlap the list's coverage. Defining the
   format now keeps R7 additive; building half the distribution machinery now
   would ship an unverifiable control.

## Consequences

* **Honest exposure bound.** Any compromised grant is usable until its window
  closes. Short TTLs make that small; the audit record (`issued_at`,
  `not_after` on every grant record) makes it measurable.
* **No hidden availability coupling.** The provider's offline guarantee is
  intact: verification needs the trust root and nothing from the network.
* **One-use still bounds damage independently.** Even inside its window, a grant
  redeems once; theft of an already-redeemed grant buys nothing
  (`already_redeemed`, and the attempt is recorded).
* **R7 has a real design constraint.** Revocation propagation must add a channel
  without breaking the offline-enforcement property — likely short-lived lists
  with fail-closed staleness, distributed alongside trust roots rather than
  polled at redemption time. That design work is explicitly out of this slice.
* **OD-009 is closed.** The open decision is answered: windows now, format
  fixed, propagation deferred — rather than a revocation mechanism that exists
  only as a TODO comment.
