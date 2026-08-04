# Architecture Decision Records

Decisions recorded in this repository, mirroring the canonical Decision Log.

## The relationship to the canonical corpus

The authoritative Decision Log lives in Google Drive (see
[CANONICAL_CORPUS.md](../../CANONICAL_CORPUS.md)) and currently holds **ADR-001 … ADR-048**:

- `07 - Connect Decision Log v0.1` — ADR-001 … ADR-033
- `07a - Connect Decision Log Addendum v0.2` — ADR-034 … ADR-048

ADRs here continue that single numbering sequence from **ADR-049**. They are not a separate
series — a decision number means the same thing in both places.

## Rules

Inherited from Documentation Constitution §3.7 and §2.1:

- **Append-only.** A decision may be marked `Superseded` by a later one. It is never silently
  rewritten or deleted.
- **No accepted architectural decision may exist only in conversation** — or only in a code
  repository. Any decision here that is architectural or constitutional must also be reflected
  in the canonical Decision Log.
- Implementation-level decisions that do not touch the Constitution, Model, or Lexicon may
  live here alone.

## Format

Match the canonical Decision Log:

```
# ADR-0NN — Title

Status: Accepted | Superseded by ADR-0MM | Proposed

Decision: what was decided, stated so it can be checked.

Rationale: why.

Rejected Alternative: what was considered and turned down, and why. (when applicable)

Consequences: what follows, including work this creates. (when applicable)

Constitutional Principle: the invariant this rests on. (when applicable)
```

## Index

| ADR | Title | Status |
|---|---|---|
| [049](ADR-049-technology-stack.md) | First-slice technology stack and Kernel isolation | Accepted |
| [050](ADR-050-grant-signature-scheme.md) | Execution-grant format and signature scheme (OD-007) | Accepted |
| [051](ADR-051-issuer-key-custody.md) | Issuer key custody for the first slice (OD-008) | Accepted |
