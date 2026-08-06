# Revocation-list conformance vectors

**These files are a specification artifact, not test fixtures** — the same discipline as
[`../../vectors/`](../../vectors/) holds for the Kernel and [`../`](../) holds for grants.

They define what ADR-052 revocation-list signing and verification do (R7): a provider-side
verifier in **any language** — which consumes lists distributed alongside the trust root — is
judged conformant against these files and ADR-052 alone, without reading the Python.

## Layout

`revocation-lists/<vector_id>.json` — one vector per file, filename equal to its `vector_id`.

Each vector is self-contained:

- `private_key_pem` / `public_key_pem` — an embedded **test-only** Ed25519 keypair, so a
  conformant implementation needs nothing but the file
- `payload` — the complete revocation list in canonical form, minus `signature`
- `expected_revocation_list` — the exact signed artifact. Ed25519 is deterministic, so
  identical fields and key must reproduce these exact bytes
- `expected_verification` — the complete structured result, including `failure_codes`
- `tampered_payload` (where present) — a mutated list; the genuine signature from
  `expected_revocation_list` must fail verification against it

The signature covers the canonical encoding of every field except `signature` itself
(ADR-052). Verification here judges signature, scheme, format version, and key attribution
only; stale-or-missing semantics are reserved to the redeemer and are deliberately not
vectored.

## Running them

```bash
.venv/bin/python -m pytest tests/test_revocation_list_vectors.py
```

## Changing them

A failing vector means the implementation or the specification is wrong. Editing `expected_*`
to match observed behaviour is a specification change and requires a Decision Log entry.
