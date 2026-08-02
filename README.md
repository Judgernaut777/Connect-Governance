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

**Milestone R0 — repository foundation.** No implementation yet.

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

## Planned stack

Recorded in [ADR-049](docs/adr/ADR-049-technology-stack.md). Python 3.11, FastAPI/Starlette,
Pydantic v2, SQLite for the first slice, SQLAlchemy 2.x + Alembic, pytest with property-based
tests where appropriate.

The **Decision Kernel is a separate, framework-independent package** with no dependency on the
web framework, the ORM, the database, the network, the system clock, randomness, mutable
global state, or any external service. That isolation is what makes an alternative Kernel
implementation substitutable against the same conformance vectors.
