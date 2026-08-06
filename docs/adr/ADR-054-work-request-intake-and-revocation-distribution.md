# ADR-054: Work Request intake and revocation-list distribution

**Status:** Accepted
**Date:** 2026-08-10
**Deciders:** Architecture review
**Related:** ADR-042 (Genesis), ADR-048 (the vertical slice), ADR-050 (grant
signature scheme), ADR-052 (grant revocation propagation), ADR-053 (Execution
Record linkage), EXECUTION_RECORD.md §5 (the R7 hook)

## Context

R7 opens the linked audit trail and the four UI surfaces. Two governance-side
questions had no answer in any repo:

1. **Where does Work Request creation live?** The `work_requests` and
   `work_request_revisions` tables existed since the initial migration, but
   only tests wrote them. Genesis already grants the founding Person
   `work_request.create`, so the authority model anticipated intake; no code
   performed it.
2. **How do revocation lists reach redeemers?** ADR-052 fixed the list format
   and explicitly deferred propagation to R7 ("revocation propagation must add
   a channel without breaking the offline-enforcement property — likely
   short-lived lists with fail-closed staleness, distributed alongside trust
   roots rather than polled at redemption time").

## Decision

1. **Work Request intake is a library function in Connect-Governance, not a
   service and not a raw write.** `create_work_request(session, *, ...)`
   builds a `CreateWorkRequest` Transition, evaluates it through the Kernel
   with `required_authority="work_request.create"` (via the existing
   `resolution.build_decision_request` + `decisions.evaluate_and_record`
   path), and persists the Work Request, its first immutable revision, and
   the Decision Record in one transaction. **Fail-closed**: any outcome other
   than Allowed raises and nothing survives the rollback — there is no
   creation path that bypasses Kernel evaluation, just as there is no
   bootstrap special case inside evaluation (ADR-042). Every instant and id
   is caller-supplied; intake invents nothing, so creation is reproducible
   and its Decision replayable like every other.
2. **Revocation lists are files distributed alongside the trust root, not
   polled at redemption time.** The governance plane builds and signs lists
   with the same canonical-JSON + Ed25519 discipline as grants (ADR-050) and
   records them immutably in `revocation_list_records`, enforcing the
   monotonic `supersedes` chain per issuer: the first list supersedes null;
   every later list must name the issuer's current head, and forks, gaps,
   and rewritten history are refused. Verification is pure and offline —
   signature, scheme, format version, and key attribution, with stable
   failure codes mirroring the grant verifier. **Stale-or-missing judgement
   is reserved to the redeemer** (ADR-052): only the redeemer holds the
   instant and the grant windows that make a list stale for a particular
   redemption, so this library deliberately does not judge it.
3. **The four surfaces' read requirements are served by a thin query layer
   plus the existing explanation projection.** `queries.py` traverses the
   already-indexed linkage ids (`grants_for_work_request`,
   `decisions_for_work_request`, `records_for_correlation`,
   `grants_by_decision_record`); `load_record` + `explanation.explain` serve
   the Decision-and-explanation surface. No schema change beyond the
   revocation-list table; nothing rendered is stored.

## Consequences

* The Work-Request UI surface (S1) has exactly one write path, and it is
  governed: a control plane that imported this library cannot create a Work
  Request the Kernel denied without forking the library.
* Revocation-list conformance vectors (`conformance/grant-vectors/
  revocation-lists/`) make the sign/verify half checkable by a provider-side
  verifier in any language, before any redeemer consumes a list.
* The redeemer half of ADR-052 — loading a list beside the trust root and
  failing closed on stale-or-missing lists for overlapping grant windows —
  is ToolConnect's R7 work, specified against the same vectors; this ADR does
  not complete it.
* ROADMAP R7 is **not** marked done by this change; that follows the
  cross-repo verification stage.
