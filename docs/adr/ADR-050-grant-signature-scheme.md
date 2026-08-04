# ADR-050 — Execution-grant format and signature scheme (OD-007)

Status: Accepted
Date: 4 August 2026
Scope: R4 — execution-grant issuance and signing

## Decision

Execution grants are **canonical-JSON payloads signed with Ed25519**, implemented in a pure
package (`connect_governance_grants`) held to the same isolation discipline as the Decision
Kernel, using the `cryptography` library (added to the `app` extra, `cryptography>=42`).

- The signed bytes are the **canonical encoding** of the payload — the same canonical JSON
  rules as the Kernel (`docs/CONFORMANCE.md` §9): sorted keys, no insignificant whitespace,
  non-ASCII literal, absent optionals as `null`. A verifier may therefore re-serialize a grant
  it received as JSON and still verify it; no wire transcript needs to be preserved.
- Ed25519 is **deterministic**: identical payload and key produce a byte-identical signature.
  Issuance is reproducible, and grant conformance vectors
  (`conformance/grant-vectors/`) can pin exact signatures — the same specification-artifact
  discipline as the Kernel vectors.
- The artifact carries `grant_format_version` (currently `"1"`), the signature scheme label,
  the base64url signature, and `issuer_key_id` = `ed25519:` + SHA-256 of the raw public key,
  so key rotation and multi-issuer deployments are auditable.
- Validity windows are RFC 3339 and **half-open** (`not_before <= t < not_after`), matching
  the Kernel's authority-window semantics. Verification takes the instant as an explicit
  caller-supplied argument (`at`); no sign or verify path reads a clock, uses randomness, or
  touches the network or filesystem. Key *generation* is the single sanctioned source of
  randomness and lives outside the package (ADR-051).

## Rationale

The integrity model (RA v0.2 §11, ADR-043) requires digital signatures and tamper evidence,
and nothing in the ecosystem implements them yet — this is the first cryptographic artifact.
Ed25519 is deterministic (a hard requirement for reproducible issuance), fast, small
(64-byte signatures, 32-byte keys), and available in a mature, audited Python binding. A pure
sign/verify core keeps the determinism and isolation claims testable by AST scan, exactly as
the Kernel's are.

## Rejected alternatives

- **RSA-PSS**: probabilistic padding makes signatures non-reproducible; larger keys and
  signatures; no compensating advantage for this artifact size.
- **HMAC / symmetric MAC**: verification would require the secret, so a provider verifying a
  grant could also forge it. Point-of-effect verification by third parties requires asymmetric
  keys.
- **Pure-Python Ed25519**: avoids a compiled dependency but re-implements primitives; the
  project pins dependencies deliberately, and `cryptography` is the maintained, audited choice.
- **JWT/JWS**: pulls in a claims framework whose semantics (exp/nbf evaluation against wall
  clock, algorithm negotiation) conflict with explicit-time verification and a closed
  algorithm set.

## Consequences

- `cryptography>=42` joins the `app` extra in `pyproject.toml`; the Kernel package still
  depends only on pydantic, and an AST test now enforces the same isolation for
  `connect_governance_grants`.
- Grant conformance vectors exist under `conformance/grant-vectors/` with an embedded test
  keypair; a provider-side verifier in any language can be judged conformant against them
  (preparation for R5).
- This resolves **OD-007** for the first slice. Revocation propagation (OD-009) and the
  provider-side redemption contract remain for R5.

## Constitutional Principle

Every Decision is deterministic and explainable (ADR-023); the grant extends the same
discipline to the first artifact that leaves the governance plane: reproducible issuance,
verifiable by anyone holding only the public key and the canonical rules.
