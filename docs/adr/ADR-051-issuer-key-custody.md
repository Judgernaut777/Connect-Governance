# ADR-051 — Issuer key custody for the first slice (OD-008)

Status: Accepted
Date: 4 August 2026
Scope: R4 — execution-grant issuance and signing

## Decision

Issuer keys are **Ed25519 private keys in PEM files with owner-only (0600) permissions**,
generated exclusively by a CLI command (`python -m connect_governance.keys generate`), and
never generated, derived, or rotated inside any sign or verify path.

- Generation refuses to overwrite an existing key file — replacing an issuer key orphans
  every grant it signed, so rotation is always a deliberate act.
- Every grant records `issuer_key_id` (ADR-050), so a verifier can distinguish "signed by an
  unknown key" from "signature invalid", and rotation is auditable from the artifacts alone.
- Key generation is the **only** module in the repository permitted to use randomness; an AST
  isolation test enforces that no grant sign/verify code imports it or any other source of
  nondeterminism.

**HSM/KMS custody, automated rotation, and revocation distribution are explicitly out of
scope for the first slice.** They are named follow-up work, not silently absent.

## Rationale

The slice needs an honest minimal answer, not an aspirational one: a single-issuer deployment
verifying against a public key it already trusts. File-based custody with strict permissions
is the smallest mechanism that is (a) real, (b) testable, and (c) truthful about its limits —
the deployment trust root is external (Genesis, ADR-042), and the issuer key file is simply
part of that external trust surface. Claiming HSM-grade custody without an HSM would be
exactly the document-code drift the corpus prohibits.

## Rejected alternatives

- **Key in the database**: mixing key material into governed state breaks the boundary between
  evidence and the means of producing it, and makes backup/export handling of secrets a
  governed-state problem.
- **Key from environment variable**: invisible to permission checks, trivially leaked via
  process inspection, and encourages generation-on-boot patterns that make issuance
  non-reproducible.
- **Deferred custody ("hardcode a test key")**: a custody answer that only works in tests is
  not a custody answer; the CLI path is exercised end-to-end in the gate.

## Consequences

- Rotation procedure for the slice: generate a new key via the CLI, distribute its public key
  and `issuer_key_id` to providers through the same external trust channel as Genesis, and
  stop issuing with the old key. Old grants remain verifiable against the old public key
  until they expire; revocation *propagation* is OD-009 and belongs to R5.
- This resolves **OD-008** for the first slice at file-based custody, with HSM/KMS and
  automated rotation explicitly deferred.

## Constitutional Principle

Genesis records an explicit external trust root rather than inventing one (ADR-042); key
custody follows the same rule — the system records and uses trust anchors, it does not
mint them.
