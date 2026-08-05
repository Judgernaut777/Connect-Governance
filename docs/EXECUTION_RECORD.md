# Execution Record Contract (R6)

> **Status:** ratified for the first vertical slice. Implemented by AgentConnect
> on branch `r6-execution-linkage` (pure record builder + hash discipline in
> `agentconnect.core.execution_records`; ledger persistence in the existing
> SQLite ledger; emission wiring in the `agentconnect-runtime` act/tool loop).
> This document is the cross-product contract; AgentConnect is the reference
> emitter.

The Reference Architecture's three-layer rule (RA v0.2 §3, ADR-037): Connect
*authorizes* (Layer 1, Connect Decision Record), providers *enforce at the
point of effect* (Layer 2, Provider Enforcement Record), and Harnesses
*execute* (Layer 3). The **Execution Record** is the Layer 3 artifact: durable
evidence of what actually ran, where, under which governance chain, and with
what outcome. It closes the ADR-048 vertical slice:

```
Work Request → Decision Record → signed execution grant (R4)
→ ToolConnect redemption + Provider Enforcement Record (R5)
→ Execution Record (this contract) → linked audit trail (R7)
```

An Execution Record is **emitted by the Harness** (AgentConnect), never by the
governance plane and never by the provider. The three record kinds are
linkable by id and by `correlation_id`, and are never interchangeable
(ADR-037).

## 1. When a record is emitted

AgentConnect's runtime act/tool loop redeems the governance execution grant at
ToolConnect's point-of-effect route (`POST /redemptions`, R5) **immediately
before every side-effecting tool call** of a governance-linked run. Every such
governed call produces exactly one Execution Record:

* `succeeded` — the grant redeemed (verified, in-window, in-scope, one-use)
  and the tool executed without error;
* `failed` — the grant redeemed but execution errored;
* `refused` — the runtime declined to execute: redemption denied, governor
  outage, wrong-grant identity echo, or no governor bound for a
  governance-linked run.

Refusals are records too — an audit trail that only contains successes is not
an audit trail.

## 2. The record

`record_format_version: "1"`. Fields (normative list; the AgentConnect test
suite pins it against this document):

| Field | Meaning |
|---|---|
| `execution_record_id` | unique record id (`execrec_…`) |
| `record_format_version` | `"1"` |
| `work_request_id` | the Layer 1 Work Request — read from the **signed grant payload**, not the runtime's say-so |
| `task_id` / `subtask_id` | AgentConnect's own ledger ids (task/subtask ≠ Work Request, ADR-036 — the binding is an explicit field, never a conflation) |
| `decision_record_id` | the Allowed Decision Record the grant was issued over |
| `grant_id` | the redeemed execution grant |
| `correlation_id` | cross-record-kind correlator (ADR-037) |
| `provider_enforcement` | the Layer 2 reference: `provider_id`, `grant_id`, `redemption_outcome` (`"redeemed"` \| `"denied:<reason>"`), `verified`, `args_hash`, `enforced_at` |
| `executor` | `executor_id`, `executor_kind`, `harness` — Layer 3 identity (a worker is not a Principal; the Principal link travels via the grant) |
| `tool` | `source_id`, `name` actually executed |
| `args_hash` | canonical-JSON SHA-256 of the arguments — **never raw arguments** |
| `outcome` | `succeeded` \| `failed` \| `refused` |
| `refusal_reason` | present on `refused` |
| `started_at` / `finished_at` | RFC 3339, caller-supplied (the builder has no clock) |
| `prev_hash` | ledger hash-chain position; `null` at the chain head |
| `record_hash` | SHA-256 seal over the canonical JSON of every other field |

## 3. Canonical form and integrity

Byte-identical discipline to the grant canonical form
(`docs/REDEMPTION_CONTRACT.md` §2): UTF-8; keys sorted by code point at every
nesting level; no insignificant whitespace; non-ASCII literal; absent
optionals encode as `null`, never omitted; non-finite floats rejected.

`record_hash = SHA-256(canonical_json(record minus record_hash))`. Records are
**append-only** in the Harness ledger and hash-chained through `prev_hash`
(chain position attached by the writer inside its write transaction — the
emitter cannot know the head). Tampering with any linkage field, the outcome,
or the enforcement reference invalidates the seal; the service write path
re-verifies the seal before storing and rejects a record that does not
verify.

## 4. The fail-closed rule (normative)

**Where a grant was required, execution without a successful redemption must
not produce a "succeeded" Execution Record.** This is enforced
constructively, not by convention: the record builder refuses to build an
`outcome: "succeeded"` record whose embedded Provider Enforcement reference is
not `verified: true` + `redemption_outcome: "redeemed"` (it raises; there is
no such record), and the runtime refuses execution outright when redemption
denies, the governor is unreachable, the redeem response echoes a different
tool identity, or no governor is bound for a governance-linked run. A
governance-linked run never falls back to the weaker contract-1.1
authorize+redeem gate, and never to ungoverned execution.

## 5. Traversal (the R7 hook)

The chain is traversable **in both directions by id**: given any of
`work_request_id`, `decision_record_id`, `grant_id`, or `correlation_id`, the
ledger returns the Execution Records naming all the others; the ToolConnect
Provider Enforcement Record is reachable from `grant_id`; the governance-side
Decision Record from `decision_record_id`. AgentConnect indexes every lifted
linkage column (`task_id`, `grant_id`, `decision_record_id`,
`correlation_id`, `work_request_id`) for exactly this. The single-identifier
cross-product query surface is R7; this contract's job is that the ids are
*there*, signed-side-sourced where they originate in governance, and sealed.

## 6. What this contract deliberately does not do

* **Signatures on Execution Records** — the seal is a hash chain inside the
  Harness ledger (tamper evidence), not a signature (non-repudiation).
  Harness-side signing keys are a post-slice decision (ADR-043 lists the full
  integrity target; the slice's cross-plane signature lives on the grant).
* **Transport** — how the record reaches a future audit-trail surface
  (pull query vs. event publication) is R7's decision. The ledger is the
  system of record either way.
* **Raw arguments** — never recorded, anywhere in the chain. Hashes only.
