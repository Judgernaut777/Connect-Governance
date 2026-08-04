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

## R6 — AgentConnect execution linkage

Associate an Execution with the Work Request and capture the **Execution Record**, reusing
AgentConnect's existing ledger rather than duplicating it.

## R7 — Linked audit trail and the four UI surfaces

End-to-end traversal from a single identifier across all three record kinds. UI surfaces,
and only these: Work Request creation and status; Decision and explanation; Marketplace and
provider activation; the linked audit trail.

## R8 — Curated Marketplace surface

Enough to activate ToolConnect as an enforcing provider and display its enforcement
classification (enforcing vs monitor-only). Deferred: third-party publishing, revenue sharing,
billing, reviews, recommendations, moderation, disputes, publisher analytics, certification.

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
