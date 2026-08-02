# Conformance vectors

**These files are a specification artifact, not test fixtures.**

They define, together with [`../docs/CONFORMANCE.md`](../docs/CONFORMANCE.md), what the Connect
Decision Kernel does. An implementation in **any language** is judged conformant against these
two artifacts alone. Reading the Python implementation is not required and confers no
authority; where the Python and these files disagree, **these files are correct**.

## Layout

`vectors/<vector_id>.json` — one vector per file, filename equal to its `vector_id`.

Each carries a `description` (what behaviour it pins down) and a `normative_reference` (the ADR
or specification section that requires it), so a reader can trace a rule back to the decision
that demands it rather than taking the vector's word for it.

`expected` is the **complete** canonical Decision, not a subset — an implementation emitting
extra or differently-ordered evidence must fail.

## Running them

Against this implementation:

```bash
.venv/bin/python -m pytest tests/test_conformance_vectors.py
```

Against another implementation: parse `input`, evaluate, encode per §9 of the specification,
and compare to `expected` byte-for-byte. The full conformance procedure is §11.

## Changing them

A failing vector means **either** the implementation deviates from the specification **or** the
specification is wrong. Neither is fixed by editing `expected` to match observed behaviour —
that would reduce the vectors to asserting that the code does what the code does.

Changing an expectation is a **specification change** and requires a Decision Log entry.
Adding a reason code requires adding a vector that defines when it is emitted; a test enforces
this.

## Coverage

26 vectors covering: the permitted path; every authority failure mode; the three time-boundary
rules (`effective_from` inclusive, `effective_until` exclusive, `revoked_at` inclusive); UTC
offset equivalence; optimistic-concurrency staleness; delegation expansion and depth, including
the at-limit boundary; every constraint kind, including spend exactly at ceiling; approval
required; approval failing to rescue absent authority; multi-failure accumulation order; policy
version echo; and multiple resolved authorities.
