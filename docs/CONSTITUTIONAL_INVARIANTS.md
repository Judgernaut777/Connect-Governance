# Constitutional invariants

What must remain true in every implementation, and the test every proposed capability must
pass before it is built.

Authoritative source: **04 - Connect Constitution** and **06 - Connect Lexicon** in the
canonical corpus. This file is a working checklist for implementers, not a replacement.

## The constitutional documentation test

Documentation Constitution §9. Every proposed core capability must answer all five cleanly:

1. What **Entity** does it introduce or extend?
2. What **Relationship** does it create or modify?
3. What **Transition** affects the governed state?
4. How does the **Decision Kernel** evaluate the Transition?
5. What immutable **Decision Record** is produced?

> A capability that cannot answer these questions cleanly either belongs outside the
> constitutional core or is not yet sufficiently understood.

Reference Architecture §15 adds: every feature proposal must additionally identify the
constitutional principles affected and the ADR or open decision needed.

## Invariants to assert in tests

These should become executable tests, not prose. R1 delivers the first of them.

### Authority
- [ ] Structure does not imply authority. Containment, provenance, and hierarchy never create it.
- [ ] Authority derives only from explicit graph relationships, and is constrained by Policy.
- [ ] Authority is never overridden. Approval **satisfies a policy condition**; it does not bypass authority.
- [ ] Roles do not inherit from Roles (ADR-008).
- [ ] Delegated work may preserve or narrow authority, never expand it (ADR-015).
- [ ] Delegation limits apply **cumulatively** across derived work, not per-request (ADR-016).

### Ownership and structure
- [ ] Every durable owned object belongs to exactly one Owner Container (ADR-003).
- [ ] A Workspace **contains** Work Requests; it does not own them (ADR-011).
- [ ] Participation, administration, and containment are not ownership.
- [ ] Organizations own Membership relationships, not Persons (ADR-004).

### The Kernel
- [ ] The Kernel decides; it does not plan, orchestrate, execute, or mutate state (ADR-025).
- [ ] Identical inputs produce byte-identical Decisions — no clock, no randomness, no globals, no I/O.
- [ ] Evaluation time and applicable revisions are supplied explicitly by the caller.
- [ ] Every Decision is explainable, producing structured evidence rather than an opaque boolean (ADR-023).
- [ ] Every Decision produces an immutable Decision Record (ADR-024).
- [ ] A future alternative Kernel, in any language, passes the same conformance vectors.

### Enforcement
- [ ] Authorizing a Work Request does **not** authorize every execution action inside it (ADR-038).
- [ ] Materially effectful actions are enforced at the resource boundary against a grant bound to their material parameters.
- [ ] Exceeding a grant results in denial or a new governed Transition — never silent acceptance.
- [ ] Monitor-only integrations are never presented as preventative controls (ADR-039).

### Time and evidence
- [ ] Governed facts carry `recorded_at`, `effective_from`, `effective_until`, `revoked_at`, `superseded_by`.
- [ ] Historical Decision explanation uses the state and versions applicable at the **original** evaluation time.
- [ ] Published governance records are append-only; history is corrected by additional records.
- [ ] A Decision evaluated against stale state never silently applies to incompatible current state.

### Identity
- [ ] Agent identity is stable and separate from its Executions (ADR-005).
- [ ] Tombstones retain only an opaque non-reusable identifier plus minimal non-personal facts (ADR-046).
- [ ] Erasure severs personal attributes and external mappings.
- [ ] Authentication is external; Connect governs identity and relationships, not credentials (ADR-006).

### Genesis
- [ ] Genesis succeeds only against empty state.
- [ ] Genesis permanently disables its own bootstrap path after success.
- [ ] After Genesis, no other path creates authority outside explicit graph relationships (ADR-042).

## Prohibited conflations

From Lexicon §9. These are naming bugs with architectural consequences:

- A Workspace **owning** Work Requests merely because it contains them
- A Role described as a permission bundle
- A Principal described as an owner because it administers or fulfills
- A Work Request described as an execution, task, prompt, workflow, plan, or intent
- A Harness described as the governance authority
- An approval described as overriding authority
- A relationship hierarchy assumed to create authority
- An Agent conflated with an Execution
- Authentication conflated with identity governance

## One honest caveat

Determinism guarantees **reproducibility and explainability**. It does not guarantee
**correctness**. The Kernel is deterministic *given registry state*, and the security outcome
still depends on the quality of the assertions in those registries — the same lesson
ToolConnect learned when an identical tool was permitted as a plain write and denied as an
external-sink write. Do not let documents or UI oversell one property as the other.
