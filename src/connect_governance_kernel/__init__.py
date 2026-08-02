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
appears. Determinism is only credible if it cannot be quietly withdrawn — a
Kernel that can read the clock cannot produce reproducible explanations of
historical decisions, which is the entire purpose of a Decision Record
(ADR-023, ADR-024).

The normative behaviour of this package is defined by ``docs/CONFORMANCE.md``
and the vectors under ``conformance/vectors/``. Those vectors are a
specification artifact: an independent implementation in any language is judged
conformant against them, without reading this code.
"""

from .canonical import canonical_json
from .evaluate import KERNEL_VERSION, STAGE_ORDER, evaluate
from .types import (
    AuthorityEvidence,
    BudgetCeiling,
    Constraint,
    Decision,
    DecisionRequest,
    DelegationContext,
    ForbidClassification,
    Outcome,
    PolicyVersionRef,
    ReasonCode,
    RequireApproval,
    RequireClassification,
    Transition,
    parse_rfc3339,
)

__all__ = [
    "AuthorityEvidence",
    "BudgetCeiling",
    "Constraint",
    "Decision",
    "DecisionRequest",
    "DelegationContext",
    "ForbidClassification",
    "KERNEL_VERSION",
    "Outcome",
    "PolicyVersionRef",
    "ReasonCode",
    "RequireApproval",
    "RequireClassification",
    "STAGE_ORDER",
    "Transition",
    "canonical_json",
    "evaluate",
    "parse_rfc3339",
]
