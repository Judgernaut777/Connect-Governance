# Decision Kernel conformance specification

**Spec version 1.** Normative for `connect_governance_kernel` and for any
independent implementation.

This document plus the vectors under [`../conformance/vectors/`](../conformance/vectors/)
define what the Decision Kernel does. **An implementation is judged conformant against these
two artifacts alone — reading the Python is not required and confers no authority.** Where
this document and the Python disagree, the document and the vectors are correct and the Python
has a bug.

Scope: R1. Signing, key custody, persistence, provider calls, and policy-language machinery are
deliberately absent from the Kernel (ADR-049).

---

## 1. What the Kernel is

A pure function:

```
evaluate(DecisionRequest) -> Decision
```

It reads no clock, generates no randomness, performs no I/O, consults no external service, and
retains no state between calls. Every fact it considers is supplied by the caller. Resolution
of those facts — traversing the organizational graph, loading policy versions, normalizing
classifications — happens **outside** the Kernel and is not specified here.

Consequences a conformant implementation must honour:

- **Determinism.** Identical input produces byte-identical output, on any machine, in any
  process, at any wall-clock time.
- **Explainability.** Every Decision carries structured evidence. An outcome with no reason
  code is not a valid Decision (ADR-023).
- **Time is an input.** `evaluation_time` is supplied, never observed. This is what allows a
  historical Decision Record to be replayed years later against the state and versions
  applicable at the original evaluation.

Determinism guarantees **reproducibility**, not **correctness**. The Kernel is deterministic
*given* the resolved inputs; whether those inputs faithfully describe reality depends on the
registries that produced them. Do not let a product surface present one as the other.

---

## 2. Data types

Encoded as JSON. Field names are normative. Unknown fields are **rejected**, not ignored — a
Kernel that silently drops an unrecognized input cannot claim its Decision was evaluated
against the inputs the caller believed it sent.

### DecisionRequest

| Field | Type | Notes |
|---|---|---|
| `transition` | Transition | the proposal being evaluated |
| `principal_active` | bool | resolved identity state of the proposer |
| `required_authority` | string | the exact authority key this Transition needs, normalized by the caller |
| `current_state_revision` | string \| null | actual current revision of the target |
| `authority_evidence` | AuthorityEvidence[] | resolved authority-bearing relationships |
| `policy_versions` | PolicyVersionRef[] | exact applicable versions |
| `constraints` | Constraint[] | normalized declarative constraints |
| `classifications` | map<string,string> | resolved classifications |
| `cumulative_state` | map<string,number> | cumulative resource state across derived work |
| `delegation` | DelegationContext \| null | present when this Transition is delegated work |
| `evaluation_time` | RFC 3339 string | **required** |
| `correlation_id` | string \| null | echoed unchanged |

The Kernel does **not** infer `required_authority` from `transition_type`. That inference is
state resolution and belongs to the caller.

### Transition

`transition_id`, `transition_type`, `proposed_by_principal_id`, `target_type`,
`target_id`(nullable), `operation`, `claims`(map), `expected_state_revision`(nullable).

### AuthorityEvidence

`relationship_id`, `relationship_type`, `principal_id`, `target_id`,
`granted_authorities`(string[]), `effective_from`(nullable), `effective_until`(nullable),
`revoked_at`(nullable).

### DelegationContext

`depth`(int), `max_depth`(int\|null), `granting_authorities`(string[]).

### Constraint — a closed vocabulary, not a language

Discriminated on `kind`. There are no expressions, no operators, and no caller-authored
predicates. **Adding a constraint kind is a versioned change to this specification**, not a
configuration change.

| `kind` | Fields (besides `constraint_id`, `policy_version`) |
|---|---|
| `require_classification` | `key`, `value` |
| `forbid_classification` | `key`, `value` |
| `budget_ceiling` | `key`, `limit`(number) |
| `require_approval` | `approval_id` |

### Decision

`outcome`, `reason_codes[]`, `transition_id`, `kernel_version`, `evaluated_at`,
`resolved_authorities[]`, `policy_versions[]`, `satisfied_conditions[]`,
`failed_conditions[]`, `required_approvals[]`, `correlation_id`.

`policy_versions` entries are formatted `"{policy_id}@{version}"`.

---

## 3. Outcomes

Exactly three (Lexicon §2): `Allowed`, `Denied`, `ApprovalRequired`.

Resolution, in this order:

1. if `failed_conditions` is non-empty → **`Denied`**
2. else if `required_approvals` is non-empty → **`ApprovalRequired`**
3. else → **`Allowed`**, and `permitted` is appended to `reason_codes`

**Approval never rescues a denial.** Approval satisfies a policy-defined condition; it does not
override authority (ADR-026). A request with no authority and a triggered approval is `Denied`,
not `ApprovalRequired` — vector `023` fixes this and it is not negotiable.

---

## 4. Evaluation order (normative)

Stages run in this order. Evaluation **does not short-circuit**: every stage runs and
contributes evidence, because an operator asking "why was this denied?" is badly served by an
answer that stops at the first problem.

Evidence is appended in the order produced. Two conformant implementations must emit identical
**sequences** of `reason_codes`, `satisfied_conditions`, and `failed_conditions` — not merely
identical sets.

| # | Stage | Emits on success | Emits on failure |
|---|---|---|---|
| 1 | structural | `structural.expected_revision_matches` | `transition.expected_revision_stale` |
| 2 | principal | `principal.active` | `principal.inactive` |
| 3 | authority | `authority.explicit_and_effective` + resolved ids | see §5 |
| 4 | delegation | `delegation.within_depth`, `delegation.subset_of_grant` | `delegation.depth_exceeded`, `delegation.would_expand_authority` |
| 5 | constraints | the `constraint_id` | see §6 |
| 6 | approval | — | `approval.required_by_policy` |

**Stage 1.** Compared only when *both* `expected_state_revision` and `current_state_revision`
are non-null. If either is null the check is satisfied — the caller is asserting it does not
require optimistic concurrency for this Transition.

**Stage 4.** Skipped entirely when `delegation` is null. When present, both checks run
independently and either may fail.

**Stage 5.** Constraints are evaluated **in the order supplied by the caller**, so the evidence
sequence is a function of the input alone. `require_approval` contributes to
`required_approvals` and emits neither satisfied nor failed evidence.

---

## 5. Authority semantics

A candidate is an `AuthorityEvidence` where **both**:

- `principal_id` equals `transition.proposed_by_principal_id`, and
- `required_authority` appears in `granted_authorities`

Authority derives **only** from explicit relationships. Nothing infers it from containment,
hierarchy, provenance, or role name.

A candidate is *in force* at `evaluation_time` `t` when all hold:

| Condition | Rule |
|---|---|
| revocation | `revoked_at` is null **or** `revoked_at > t` |
| lower bound | `effective_from` is null **or** `effective_from <= t` |
| upper bound | `effective_until` is null **or** `t < effective_until` |

**Window semantics are half-open: `[effective_from, effective_until)`.** `t == effective_from`
is in force (vector `008`); `t == effective_until` is **not** (vector `009`).

**Revocation is inclusive: `t == revoked_at` is revoked** (vector `010`). The two boundaries
differ deliberately — revocation is protective, so its boundary resolves against the actor.

If at least one candidate is in force: emit `authority.explicit_and_effective`, and list every
in-force `relationship_id` in `resolved_authorities` **in input order**.

Otherwise emit `authority.explicit_and_effective` as failed, and:

- if there were **no candidates at all** → `authority.none_explicit`
- if candidates existed but none in force → emit the applicable codes in this fixed order:
  `authority.revoked`, then `authority.not_yet_effective`, then `authority.expired`, each at
  most once. The fixed order makes the sequence reproducible when several candidates fail for
  different reasons.

---

## 6. Constraint semantics

| Kind | Satisfied when | Failure code |
|---|---|---|
| `require_classification` | `classifications[key] == value` | `classification.required_absent` |
| `forbid_classification` | `classifications[key] != value` (including absent) | `classification.forbidden_present` |
| `budget_ceiling` | `cumulative_state[key]` (default `0`) `<= limit` | `budget.ceiling_exceeded` |
| `require_approval` | n/a — appends `approval_id` to `required_approvals` | n/a |

**Ceilings are exceeded strictly above the limit.** Spend exactly equal to the limit is
permitted (vector `020`); the same rule applies to delegation depth, where `depth == max_depth`
is permitted (vector `017`). Ceilings are cumulative across derived work (ADR-016).

---

## 7. Reason codes

Stable, versioned wire values. Prose is a projection; stored evidence must never depend on
rendered prose.

```
transition.expected_revision_stale     principal.inactive
authority.none_explicit                authority.not_yet_effective
authority.expired                      authority.revoked
delegation.would_expand_authority      delegation.depth_exceeded
classification.required_absent         classification.forbidden_present
budget.ceiling_exceeded                approval.required_by_policy
permitted
```

Every code above is exercised by at least one vector, and a test enforces that — a code cannot
be added to the contract without a vector defining when it is emitted.

---

## 8. Timestamps

RFC 3339, and a **UTC offset is required**. A timestamp without an offset is rejected rather
than assumed to be UTC: silently guessing a timezone would make a Decision depend on a fact the
caller never supplied.

`Z` and `+00:00` denote the same instant. Comparison is instant comparison after parsing, not
string comparison — `2026-08-03T13:00:00+01:00` and `2026-08-03T12:00:00Z` are equal (vector
`011`).

`evaluated_at` echoes `evaluation_time` **exactly as supplied**, without normalization.

---

## 9. Canonical encoding

Determinism is only checkable if two Decisions can be compared byte-for-byte.

- UTF-8; object keys sorted lexicographically by code point
- no insignificant whitespace; separators are `,` and `:`
- non-ASCII emitted literally, not escaped
- sequences preserve order — **order is evidence, not presentation**
- absent optional fields encode as `null`, never omitted

---

## 10. Vector format

One JSON file per vector in `conformance/vectors/`, filename equal to `vector_id`.

```json
{
  "vector_id": "001-allow-minimal",
  "description": "…what this pins down…",
  "normative_reference": "…the ADR or section that requires it…",
  "spec_version": "1",
  "kernel_version_min": "0.0.1",
  "input":    { "…a complete DecisionRequest…" },
  "expected": { "…the complete canonical Decision…" }
}
```

`expected` is the **complete** Decision, not a subset: an implementation that produced extra or
differently-ordered evidence would otherwise pass.

`normative_reference` is required so a reader can trace a behaviour to the decision that
requires it, instead of taking the vector's word for it.

---

## 11. Judging an implementation conformant

1. For every vector: parse `input`, evaluate, encode per §9, and compare to `expected`. All
   must match exactly.
2. Replay: evaluating the same input repeatedly must yield identical bytes.
3. Key order: reordering the input object's keys must not change the Decision.
4. Non-mutation: evaluation must not modify its input.
5. Coverage: every outcome and every reason code in §7 must be exercised.

A failing vector means **either** the implementation deviates from this specification **or**
the specification is wrong. Neither is fixed by editing `expected` to match observed behaviour.
Changing a vector's expectation is a specification change and requires a Decision Log entry.

---

## 12. Not in scope for spec version 1

Absent from the Kernel by decision, not by omission (ADR-049): grant signing and signature
verification; key custody, rotation, and revocation distribution; persistence; provider
communication; a general policy language or expression evaluator; approval workflow mechanics
beyond emitting the requirement; and clock access of any kind.

Grant signing arrives at R4 and depends on OD-007 (grant format and signature scheme) and
OD-008 (key custody, rotation, revocation, and the verification trust model). Both are open.
