# Connect Ecosystem Reconciliation & Integration Roadmap

> **Status:** Active. This roadmap governs work in this repository until the corpus
> is ratified (ADR-045). It exists to prevent the architecture from being re-decided
> piecemeal in PRs.

The corpus defines a four-layer ecosystem: **Connect** (governance),
**AgentConnect** (execution coordination), **BrainConnect** (memory),
**ToolConnect / ComputeConnect / Marketplace** (capability plane). The peer
products ship today; this repository is the governance plane they will
integrate with. Each milestone below is sized to land as one coherent,
reviewable unit with a green test gate.

- [x] **R0 — Repository foundation.** Canonical corpus pointers, boundary
  statement, constitutional invariants, ADR mirror, technology stack (ADR-049).
- [x] **R1 — Decision Kernel.** Pure, deterministic `evaluate()` over explicit
  inputs; conformance vectors; AST-enforced isolation (no clock, no RNG, no I/O).
- [x] **R2 — Governed state + persistence.** SQLite schema (Organizations,
  Workspaces, Persons, Agents, Authority Relationships, Work Requests +
  revisions), Alembic migrations, Genesis bootstrap (ADR-042).
- [x] **R3 — Decision Records, replay, explanation.** Every evaluation persisted
  in canonical form; byte-exact replay; operator/proof views as on-read
  projections (ADR-023, ADR-024).
- [x] **R4 — Execution grants.** Ed25519-signed grants over canonical payloads
  from Allowed Decision Records (ADR-038, ADR-050); pure sign/verify package with
  Kernel-grade isolation; file-based issuer keys (ADR-051); grant conformance
  vectors gv-001…gv-005.
- [x] **R5 — Provider redemption contract.** Consumer-facing redemption contract
  ([docs/REDEMPTION_CONTRACT.md](REDEMPTION_CONTRACT.md)): offline verification
  against a configured trust root, caller-supplied time, scope binding, atomic
  one-use, and the Provider Enforcement Record. OD-009 resolved by
  [ADR-052](adr/ADR-052-grant-revocation-propagation.md) (short validity
  windows; revocation-list format defined, propagation deferred to R7).
  Reference consumer: **ToolConnect** implements this contract on its
  `r5-grant-redemption` branch — the first Provider Enforcement Record, with
  byte-compatibility proven against gv-001…gv-005, not cross-repo imports.
- [ ] **R6 — Execution Records.** AgentConnect closes the loop: what actually
  ran, correlated to the Decision Record and grant (ADR-037).
- [ ] **R7 — Revocation propagation.** Distribute the ADR-052 revocation-list
  format to providers without breaking offline enforcement.
- [ ] **R8 — Marketplace activation surface.** Governed discovery and activation
  of capabilities.
- [ ] **R9 — Hardening.** HSM/KMS key custody, rotation choreography, scale-out
  persistence.
