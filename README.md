# Connect-Governance

The organizational governance plane of **Connect** — the Decision Kernel, governance state,
authorization Decisions, and execution-grant issuance.

> **Connect authorizes organizational commitments. Providers enforce authorization at the
> point of effect. AgentConnect coordinates execution within the authorized boundary. The
> Marketplace makes governed capabilities discoverable, activatable, usable, and commercially
> viable.**

## Read this before changing anything

1. [CANONICAL_CORPUS.md](CANONICAL_CORPUS.md) — where the authoritative architecture lives
   (it is **not** this repository)
2. [REPOSITORY_BOUNDARY.md](REPOSITORY_BOUNDARY.md) — what this repository does and does not own
3. [docs/ROADMAP.md](docs/ROADMAP.md) — the reconciliation and integration roadmap (R0–R9)
4. [docs/CONSTITUTIONAL_INVARIANTS.md](docs/CONSTITUTIONAL_INVARIANTS.md) — what must remain
   true, and the test every proposed capability must pass
5. [docs/adr/](docs/adr/) — decisions recorded here, mirroring the canonical Decision Log

## Status

**Milestones R0–R8 merged** (see [docs/ROADMAP.md](docs/ROADMAP.md)):

- **R0/R0b** — repository foundation; Python scaffolding with AST-enforced Kernel isolation
- **R1** — pure, deterministic `evaluate()` Decision Kernel + 26 conformance vectors
- **R2** — governed state (SQLAlchemy models, Alembic migrations) + Genesis trust-root operation
- **R3** — immutable, byte-replayable Decision Records + explanation as a read-time projection
- **R4** — Ed25519 execution-grant issuance and signing
- **R5** — ToolConnect point-of-effect redemption
- **R6** — AgentConnect execution linkage
- **R7** — linked audit trail and the four UI surfaces
- **R8** — curated marketplace: listings, governed provider activation, fail-closed
  enforcement classification

Latest local gate: **316 passed**. Next up: **R9 — the reconciliation pass** (resolve each
existing AgentConnect governance-like capability as preserved, integrated, or reclassified,
then promote the corpus to Candidate per ADR-045).

Running the gate needs the `[app]` extra — the Kernel itself depends only on `pydantic`, but
the persistence, migration, and grant-signing tests import SQLAlchemy, Alembic, and
`cryptography`:

```bash
pip install -e ".[app,dev]" && python3 -m pytest
```

The corpus this repository implements is **Draft, not ratified** (ADR-045). Do not rename
APIs, delete capabilities, or restructure other products' repositories because a draft
document says so.

## Naming

| Name | Means |
|---|---|
| **Connect** | the governance product and control plane |
| **Connect-Governance** | this repository — the governance-plane implementation |
| **Connect Ecosystem** | Connect + AgentConnect + BrainConnect + ToolConnect + ComputeConnect + Marketplace + integrations |

See ADR-034. The peer products already exist and ship; this repository integrates with them
rather than replacing them.

## Stack

Recorded in [ADR-049](docs/adr/ADR-049-technology-stack.md). Python 3.11, FastAPI/Starlette,
Pydantic v2, SQLite for the first slice, SQLAlchemy 2.x + Alembic, pytest with property-based
tests where appropriate.

The **Decision Kernel is a separate, framework-independent package** with no dependency on the
web framework, the ORM, the database, the network, the system clock, randomness, mutable
global state, or any external service. That isolation is what makes an alternative Kernel
implementation substitutable against the same conformance vectors.
