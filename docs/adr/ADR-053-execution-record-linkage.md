# ADR-053: Execution Record linkage — Harness-emitted, ledger-sealed, grant-sourced ids

**Status:** Accepted (resolves OD-013 for the slice)
**Date:** 2026-08-05
**Deciders:** Architecture review
**Related:** ADR-037 (three-record taxonomy), ADR-038 (point-of-effect
enforcement), ADR-036 (no AgentConnect API renames), ADR-043 (integrity),
ADR-048 (the vertical slice), REDEMPTION_CONTRACT.md, EXECUTION_RECORD.md

## Context

R6 closes the ADR-048 loop: after governance authorizes (Decision Record),
issues (signed grant), and ToolConnect enforces (Provider Enforcement Record),
AgentConnect — the Harness — must leave the Layer 3 artifact: the **Execution
Record**. **OD-013** asked how records that live in *different products'*
stores get linked across the boundary, and the R6 roadmap line adds a second
constraint: *reuse AgentConnect's existing ledger rather than duplicating it.*

The options for cross-boundary linking were:

1. **Callback registration** — the Harness posts the record back to
   Connect-Governance. Rejected: it makes execution evidence depend on a live
   governance-plane connection (the same availability coupling ADR-052 refuses
   for providers), and governance does not execute, so it cannot vouch for
   what ran.
2. **Shared event bus as system of record** — records exist only as bus
   events. Rejected: the bus is a transport, not a store of record; R7 needs
   something queryable per product.
3. **Id-carrying, self-describing records** (chosen) — each record kind names
   the ids of the others it binds to, inside its own store, sealed; traversal
   is a read-time join across products on those ids (assembled in R7).

## Decision

1. **The Execution Record is emitted by the Harness and stored in
   AgentConnect's existing SQLite ledger** (append-only `execution_records`
   table, indexed on every linkage id). No new store, no duplicated ledger.
2. **Linkage ids are sourced from the signed grant payload wherever they
   originate in governance** (`work_request_id`, `decision_record_id`,
   `grant_id`, `correlation_id`, `provider_id`). The Harness records the
   issuer's attestation, not its own claims; a runtime that fabricated linkage
   would have to forge the grant first, and the redemption would fail.
3. **Integrity is the ecosystem's existing canonical-JSON + SHA-256
   discipline**: `record_hash` seals every field; `prev_hash` chains records
   in the ledger; the chain position is attached by the writer inside the
   write transaction. Execution Records are hash-sealed (tamper evidence),
   deliberately **not signed** in the slice — Harness key custody is deferred
   the same way ADR-051 deferred provider-side key questions.
4. **Fail-closed is constructive**: a `succeeded` record cannot be built
   without a verified, redeemed Provider Enforcement reference; a
   governance-linked run without a working redemption path refuses to execute
   and records a `refused` record.
5. **Terminology per ADR-036/045**: the record binds AgentConnect's
   `task_id`/`subtask_id` to the governance `work_request_id` as *explicit
   fields side by side* — no API renames, no conflation of task with Work
   Request.

## Consequences

* **OD-013 is closed for the slice**: cross-boundary linking is id-carrying
  records plus read-time joins; R7 builds the single-identifier query surface
  on top. A generalized record-federation protocol remains out of scope.
* AgentConnect's `toolconnect_governor` contract stays **1.1, unbumped**: the
  governance redemption is an additive method on the concrete
  `ToolConnectGovernor`, not a Protocol change — existing governors remain
  valid.
* Any Harness (not only AgentConnect) can emit conformant Execution Records
  against `EXECUTION_RECORD.md`; byte-compatibility is checkable against the
  canonical-form rules without importing either repo.
* When Harness-side signing keys are later decided (ADR-043's non-repudiation
  target), the record shape admits a signature envelope additively; the hash
  seal remains the inner integrity layer.
