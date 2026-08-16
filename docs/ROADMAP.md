# Reconciliation and integration roadmap

Implements Reference Architecture **v0.2 §14**. This replaces v0.1's greenfield milestone
sequence, which assumed the peer products did not exist.

The peer products **do** exist, ship, and are pinned in the Connect-Ecosystem manifest. Every
milestone below integrates with them rather than reimplementing them.

## R0 — Repository foundation ✅

Language-neutral. ADR directory, canonical-corpus pointer, constitutional invariant checklist,
this roadmap, repository boundary statement.

## R1 — Kernel package and conformance vectors ✅

The framework-independent Decision Kernel with its pure `evaluate()` contract, plus the first
conformance vectors — **26 vectors + `docs/CONFORMANCE.md` spec v1**. **Determinism and isolation are tested before any persistence or API
exists** — that ordering is deliberate, because the Kernel's isolation is the property that
makes a future alternative implementation substitutable.

The Kernel must not depend on FastAPI/Starlette, SQLAlchemy/SQLite, network access, mutable
global state, the system clock, random generation, or any external service. Evaluation time
and applicable revisions are supplied explicitly by the caller.

## R2 — Minimal governed state ✅

Only what the vertical slice requires: Organization, Workspace, Person, Agent, Work Request
and revision, and the authority relationships needed to authorize one Transition. Genesis
establishes the trust root (ADR-042).

Not the full entity model. Not the full transition catalogue.

## R3 — Decision Record and explanation ✅

Immutable Connect Decision Records with stable machine-readable reason codes and the
explanation projection.

The explanation view is a defining product surface, not an administrative afterthought — and
its hardest problem is expressing expert evidence (resolved authorities, relationships
traversed, policy versions, failed conditions) to a non-expert operator. Treat that as a
product problem, not a formatting one.

## R4 — Execution grant issuance and signing ✅

Signed, versioned grants bound to: Work Request and revision, requesting Principal or Agent,
Organization and Workspace, permitted provider, permitted operations, material arguments or
argument constraints, data classifications, budget or consumption limits, time limits and
expiration, delegation limits, Policy version, Kernel version, revocation state.

Delivered: the pure `connect_governance_grants` package (Ed25519 sign/verify over canonical
JSON, same isolation discipline as the Kernel, verified against caller-supplied instants —
never a clock); issuance from **Allowed** Decision Records only, persisted immutably in
`execution_grant_records`; file-based issuer-key custody with 0600 permissions via
`python -m connect_governance.keys`; grant conformance vectors in
`conformance/grant-vectors/`. **OD-007 and OD-008 are resolved by ADR-050 and ADR-051**
(Ed25519 via `cryptography`; file-based custody for the slice, HSM/KMS explicitly deferred).

## R5 — ToolConnect point-of-effect redemption ✅

Integrate against ToolConnect's **existing** contract 1.1 grant redemption. This is an
integration, not a reimplementation: ToolConnect already implements argument-bound single-use
grants with atomic redemption immediately before execution, plus an optional stdio enforcement
gateway for callers that cannot be trusted to redeem voluntarily.

Produces the first **Provider Enforcement Record**.

Delivered: the consumer-facing redemption contract —
[docs/REDEMPTION_CONTRACT.md](REDEMPTION_CONTRACT.md) — defining the artifact, mandatory
offline verification against a configured trust root (absent root = deny), caller-supplied
time with half-open windows, scope binding, atomic one-use, and the Provider Enforcement
Record every attempt must leave. **OD-009 is resolved by
[ADR-052](adr/ADR-052-grant-revocation-propagation.md)**: short validity windows are the
revocation mechanism for the slice, the revocation-list format is defined, and propagation is
deferred to R7 rather than half-built. Reference consumer: **ToolConnect** implements this
contract on its `r5-grant-redemption` branch (vendored verifier, byte-compatible with
gv-001…gv-005 — interop through the artifact, not cross-repo imports).

## R6 — AgentConnect execution linkage ✅

Associate an Execution with the Work Request and capture the **Execution Record**, reusing
AgentConnect's existing ledger rather than duplicating it.

Delivered: the consumer-facing Execution Record contract —
[docs/EXECUTION_RECORD.md](EXECUTION_RECORD.md) — defining the record shape
(`record_format_version: "1"`), the same canonical-JSON/SHA-256 seal discipline as the
grants, the constructive fail-closed rule (no `succeeded` record without a verified,
redeemed Provider Enforcement Record), and bidirectional id traversal across the full
chain *work request → decision → grant → redemption → execution*. **OD-013 is resolved
for the slice by [ADR-053](adr/ADR-053-execution-record-linkage.md)**: cross-boundary
linking is id-carrying records with linkage ids sourced from the signed grant payload,
joined at read time. Reference emitter: **AgentConnect** on branch `r6-execution-linkage`
(pure `agentconnect.core.execution_records` builder, append-only `execution_records`
ledger table, and the runtime act/tool loop emitting on every governance-grant
redemption — success, failure, and refusal alike).

## R7 — Linked audit trail and the four UI surfaces ✅

End-to-end traversal from a single identifier across all three record kinds. UI surfaces,
and only these: Work Request creation and status; Decision and explanation; Marketplace and
provider activation; the linked audit trail.

Delivered, across four repos (each verified by an independent cross-repo check that
resolved one end-to-end trail by each of the four linkage identifiers and reproduced
tamper-evidence on read):

* **Here:** kernel-evaluated, fail-closed Work Request intake
  (`connect_governance.work_requests.create_work_request` — nothing persists on denial);
  the `connect_governance.queries` read layer over the already-indexed linkage columns;
  ADR-052 revocation-list issuance (`connect_governance.revocations`: issuer-signed,
  monotonic `supersedes` chaining, persisted in `revocation_list_records`, conformance
  vectors rv-001/rv-002). **Intake and the revocation distribution channel are decided by
  [ADR-054](adr/ADR-054-work-request-intake-and-revocation-distribution.md).**
* **ToolConnect:** redemption-side revocation enforcement — `revoked` /
  `stale_revocation_list`, fail-closed on stale-or-unverifiable lists only for grants
  whose windows overlap list coverage, denials recorded as Provider Enforcement Records;
  the governance trust root and revocation list are wired into the CLI
  (`--gov-trust-root` / `--gov-revocation-list`).
* **AgentConnect:** read-side chain verification of the execution-record ledger
  (`ExecutionRecordLedger.verify_chain()` — per-record seal re-verification plus
  `prev_hash` linkage, first break reported).
* **Connect-Control:** the four surfaces as server-rendered pages over a read-only
  audit projection (the three SQLite stores opened `mode=ro`, joined by the linkage
  ids, chains verified on read). The projection is an explicit, temporary exception to
  the thin-control-plane "no direct database access" rule, expiring when per-plane
  record-read APIs land (earmarked R8/R9).

## R8 — Curated Marketplace surface ✅

Enough to activate ToolConnect as an enforcing provider and display its enforcement
classification (enforcing vs monitor-only). Deferred: third-party publishing, revenue sharing,
billing, reviews, recommendations, moderation, disputes, publisher analytics, certification.

Delivered, across three repos (independently verified end to end — listing → kernel
decision → activation → live classification — with every fail-closed negative
reproduced):

* **Here:** the curated marketplace model — operator-authored `ProviderListing`
  (kernel-evaluated `CreateProviderListing`, authority `provider.list`) and governed
  `ProviderActivation` (`ActivateProvider`, authority `provider.activate`; fail-closed,
  nothing persists on denial). Enforcement classification is a **declared property with
  a stored evidence basis** (RA §8, ADR-039/040/041): an `enforcing` listing without
  classification evidence is refused before kernel evaluation. **Decided by
  [ADR-055](adr/ADR-055-curated-marketplace-model.md)** — OD-010 (entitlement/pricing)
  and OD-011 (certification programs) explicitly remain open; `provider.deactivate` is
  reserved, lifecycle writes deferred.
* **ToolConnect:** `/health` surfaces governance trust-root posture
  (`gov_trust_root.configured` / `key_ids`, PEM never exposed) and `gov_provider_id` —
  the HTTP-observable evidence leg an enforcing classification requires.
* **Connect-Control:** the marketplace surface — listings, operator-triggered
  activation through the governance package, and a fail-closed classification badge
  (enforcing only with all four evidence legs: stored evidence, active activation with
  its Decision Record, live trust-root + intact audit chain, observable Provider
  Enforcement Records; anything missing degrades to `unverified`; monitor-only is never
  presented as preventative, per ADR-039).

## R9 — Reconciliation pass

Per ADR-035 and OD-012: resolve the disposition of each existing AgentConnect governance-like
capability — approvals, delegation envelopes, budgets, privacy controls, audit — as
**preserved**, **integrated**, or **reclassified**. Then promote the corpus to Candidate per
ADR-045.

---

## Out of scope for the first slice

Self-governance (ADR-033, "use Connect to build Connect") remains the direction of travel but
is deliberately not part of this slice.

Also out of scope: production database topology, distributed deployment model, generalized
policy language, full marketplace architecture. SQLite is the first-slice persistence
mechanism, **not a permanent constitutional requirement**.
