# ADR-049 — First-slice technology stack and Kernel isolation

Status: Accepted
Date: 3 August 2026
Scope: the first Connect-Governance vertical slice (ADR-048)

## Decision

The first Connect-Governance implementation uses:

- **Python 3.11**
- **FastAPI or Starlette** for the HTTP governance API
- **Pydantic v2** for strict public and domain schemas
- **SQLite** for the first vertical slice
- **SQLAlchemy 2.x with Alembic** for persistence and migrations
- **pytest**, with property-based tests where appropriate

The **Decision Kernel must be implemented as a separate, framework-independent package** with
no dependency on:

- FastAPI or Starlette
- SQLAlchemy or SQLite
- network access
- mutable global state
- system clock access
- random generation
- external services

The Kernel receives normalized, explicit inputs — **including the effective evaluation time and
the exact applicable revisions** — and returns a deterministic structured Decision. State
resolution, persistence, signing, API behaviour, and provider communication all belong outside
the Kernel.

## Rationale

The ecosystem is already Python-based, and the first vertical slice requires direct integration
with ToolConnect (point-of-effect grant redemption) and AgentConnect (execution linkage). The
objective is to validate the governance-to-enforcement architecture with **minimal integration
friction**, not to select a permanent production stack.

The Kernel is isolated because determinism is only credible if it is structurally enforced.
A Kernel that can read the clock, generate randomness, reach the network, or consult mutable
global state cannot be shown to produce identical Decisions from identical inputs — and
therefore cannot produce reproducible explanations of historical decisions, which is the whole
point of a Decision Record.

## Consequences

**Conformance vectors become a first-class artifact.** The Kernel contract must remain
sufficiently isolated that a future alternative implementation — in any language — can be
substituted and tested against the same vectors. Vectors are delivered with R1, before any
persistence or API exists.

**Time is an input, not an ambient fact.** Every caller must supply `evaluation_time`
explicitly. Historical Decision explanation uses the state and versions applicable at the
original evaluation time.

**Two properties become testable rather than asserted:** determinism (identical inputs →
byte-identical Decisions) and isolation (the Kernel package imports nothing from the web,
persistence, or I/O layers). Both belong in R1's test suite; the import-boundary check should
be an automated scan so a future contributor cannot quietly reintroduce a dependency.

## Explicitly NOT decided

This decision does **not** select:

- a production database topology
- a distributed deployment model
- a generalized policy language
- a full marketplace architecture

**SQLite is the first-slice persistence mechanism, not a permanent constitutional
requirement.** Reference Architecture v0.2 §12 states the constitutional requirement as
conceptual and behavioural, not vendor-specific: a later relational, graph, event-store, or
hybrid topology may replace SQLite without constitutional change.

This decision is also **not** authorization to build the entire v0.1 Reference Architecture.
Scope remains the vertical slice defined in ADR-048.

## Constitutional Principle

The Decision Kernel decides; it does not plan, orchestrate, execute, or directly mutate
governed state (ADR-025). Every Decision is deterministic and explainable (ADR-023), and
produces an immutable Decision Record (ADR-024).
