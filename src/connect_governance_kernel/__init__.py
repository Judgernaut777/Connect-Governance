"""The Connect Decision Kernel — deterministic, framework-independent.

This package evaluates a proposed governance state Transition and returns a
structured Decision. It decides; it does not plan, orchestrate, execute, or
mutate governed state (ADR-025).

ISOLATION CONTRACT (ADR-049). This package must NOT depend on:

  * FastAPI or Starlette
  * SQLAlchemy or SQLite
  * network access
  * mutable global state
  * system clock access
  * random generation
  * external services

Every input the Kernel needs is supplied explicitly by the caller, including
``evaluation_time`` and the exact applicable revisions. State resolution,
persistence, signing, API behaviour, and provider communication all belong
outside this package.

The isolation is structural, not aspirational: ``tests/test_kernel_isolation.py``
scans this package's AST and fails the gate if a forbidden import or an ambient
source of nondeterminism (``datetime.now``, ``time.time``, ``random``, ``uuid4``)
appears. The reason is that determinism is only credible if it cannot be quietly
withdrawn — a Kernel that can read the clock cannot produce reproducible
explanations of historical decisions, which is the entire purpose of a Decision
Record (ADR-023, ADR-024).

A future alternative Kernel, in any language, must pass the same conformance
vectors. Those vectors are a first-class artifact, not a test-suite detail.
"""

from .types import (
    Decision,
    DecisionRequest,
    Outcome,
    ReasonCode,
)

__all__ = [
    "Decision",
    "DecisionRequest",
    "Outcome",
    "ReasonCode",
    "KERNEL_VERSION",
]

#: Recorded on every Decision so a historical Decision Record can be replayed
#: against the Kernel version that produced it.
KERNEL_VERSION = "0.0.1"
