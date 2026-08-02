"""Run every conformance vector against the Kernel.

The vectors under ``conformance/vectors/`` are a specification artifact, not
fixtures generated from this implementation. This module is one *consumer* of
that specification; an implementation in another language is judged conformant
by consuming the same files and producing the same expected output.

A failure here means one of two things, and they are not the same:
  * the Kernel deviates from the specification, or
  * the specification is wrong.
Neither is fixed by editing the expected output to match observed behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from connect_governance_kernel import DecisionRequest, canonical_json, evaluate

VECTOR_DIR = Path(__file__).resolve().parents[1] / "conformance" / "vectors"

REQUIRED_VECTOR_KEYS = {
    "vector_id",
    "description",
    "normative_reference",
    "spec_version",
    "kernel_version_min",
    "input",
    "expected",
}


def load_vectors() -> list[dict]:
    files = sorted(VECTOR_DIR.glob("*.json"))
    assert files, f"no conformance vectors found in {VECTOR_DIR}"
    return [json.loads(p.read_text(encoding="utf-8")) for p in files]


VECTORS = load_vectors()


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["vector_id"])
def test_vector_is_well_formed(vector: dict) -> None:
    """A vector must be self-describing enough to be a specification.

    Each carries a normative reference, so a reader can trace the expected
    behaviour back to the decision that requires it rather than taking the
    vector's word for it.
    """
    missing = REQUIRED_VECTOR_KEYS - vector.keys()
    assert not missing, f"{vector.get('vector_id')} missing keys {sorted(missing)}"
    assert vector["description"].strip()
    assert vector["normative_reference"].strip()


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["vector_id"])
def test_kernel_matches_vector(vector: dict) -> None:
    decision = evaluate(DecisionRequest.model_validate(vector["input"]))
    actual = json.loads(canonical_json(decision))
    expected = vector["expected"]
    assert actual == expected, (
        f"\nvector: {vector['vector_id']} — {vector['description']}"
        f"\nnormative reference: {vector['normative_reference']}"
        f"\nexpected: {json.dumps(expected, indent=2, sort_keys=True)}"
        f"\nactual:   {json.dumps(actual, indent=2, sort_keys=True)}"
    )


def test_vector_ids_are_unique_and_match_filenames() -> None:
    ids = [v["vector_id"] for v in VECTORS]
    assert len(ids) == len(set(ids)), "duplicate vector_id"
    for path in sorted(VECTOR_DIR.glob("*.json")):
        vector = json.loads(path.read_text(encoding="utf-8"))
        assert vector["vector_id"] == path.stem, (
            f"{path.name} declares vector_id {vector['vector_id']!r}; "
            "filename and id must agree so a failure names a findable file"
        )


def test_suite_covers_every_outcome_and_reason_code() -> None:
    """The vector set is a specification; gaps in it are gaps in the spec.

    Every canonical outcome and every declared reason code must be exercised by
    at least one vector, so a reason code cannot be added to the contract
    without a vector defining when it is emitted.
    """
    from connect_governance_kernel import Outcome, ReasonCode

    seen_outcomes = {v["expected"]["outcome"] for v in VECTORS}
    assert seen_outcomes == {o.value for o in Outcome}, (
        f"outcomes not covered: {sorted({o.value for o in Outcome} - seen_outcomes)}"
    )

    seen_codes = {c for v in VECTORS for c in v["expected"]["reason_codes"]}
    missing = {c.value for c in ReasonCode} - seen_codes
    assert not missing, f"reason codes with no vector: {sorted(missing)}"
