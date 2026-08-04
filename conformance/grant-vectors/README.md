# Grant conformance vectors

**These files are a specification artifact, not test fixtures** — the same discipline as
[`../vectors/`](../vectors/) holds for the Kernel.

They define what execution-grant signing and verification do (R4, ADR-050): a provider-side
verifier in **any language** — which R5 needs — is judged conformant against these files and
ADR-050 alone, without reading the Python.

## Layout

`grant-vectors/<vector_id>.json` — one vector per file, filename equal to its `vector_id`.

Each vector is self-contained:

- `private_key_pem` / `public_key_pem` — an embedded **test-only** Ed25519 keypair, so a
  conformant implementation needs nothing but the file
- `payload` — the complete grant payload in canonical form
- `expected_grant` — the exact signed artifact (payload + Ed25519 signature). Ed25519 is
  deterministic, so identical payload and key must reproduce these exact bytes
- `verify_at` — the caller-supplied instant verification is judged against (never a clock)
- `expected_verification` — the complete structured result, including `failure_codes`
- `tampered_payload` (where present) — a mutated payload; the genuine signature from
  `expected_grant` must fail verification against it

## Running them

Against this implementation:

```bash
.venv/bin/python -m pytest tests/test_grant_vectors.py
```

Against another implementation: sign `payload` with `private_key_pem` and compare to
`expected_grant` byte-for-byte; verify `expected_grant` (or `tampered_payload` with the
original signature) against `public_key_pem` at `verify_at` and compare to
`expected_verification`.

## Changing them

A failing vector means the implementation or the specification is wrong. Editing `expected_*`
to match observed behaviour is a specification change and requires a Decision Log entry.

## Coverage

Deterministic sign/verify of a complete payload; tamper evidence (any mutation fails);
the validity-window boundary rules (`not_before` inclusive, `not_after` exclusive,
caller-supplied instant).
