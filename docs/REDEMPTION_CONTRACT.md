# Execution-Grant Redemption Contract (R5)

> **Status:** ratified for the first vertical slice. Implemented by ToolConnect on
> branch `r5-grant-redemption`. Governance-side issuance is R4; this document is the
> consumer-facing half — what a provider must do to honor an execution grant at the
> point of effect.

The Reference Architecture's rule (RA v0.2 §7): **Connect authorizes; providers
enforce at the point of effect.** An execution grant is how an authorization travels
from the governance plane to a provider without the provider ever calling back into
Connect at decision time. Redemption is the act by which a provider turns a presented
grant into one — and only one — authorized action, and leaves evidence that it did.

This contract is deliberately small. It defines the artifact, the verification a
provider MUST perform, the scope binding, the one-use rule, and the record a provider
MUST leave. It does not define transport: how a caller obtains a grant and presents it
is the caller's business.

## 1. The artifact

An execution grant is a JSON object with three fields:

```json
{
  "payload": { "...": "signed content (GrantPayload)" },
  "signature_scheme": "Ed25519",
  "signature": "<base64url, no padding, 64 bytes>"
}
```

The payload's signed fields are defined by `connect_governance_grants.GrantPayload`
(`grant_format_version: "1"`). The fields a redeemer MUST bind on:

| Field | Binding |
|---|---|
| `grant_id` | unique redemption key; drives one-use semantics |
| `decision_record_id` | the Allowed Decision Record that authorized this grant |
| `correlation_id` | correlation across record kinds (ADR-037) |
| `issuer_key_id` | `ed25519:` + sha256 of the issuer's raw public key |
| `provider_id` | the single provider this grant may be redeemed against |
| `requesting_principal_id` | the principal that must present the grant |
| `permitted_operations` | closed list; anything else is denied |
| `argument_constraints` | material argument bindings (§4) |
| `not_before` / `not_after` | validity window, RFC 3339, half-open |
| `revocation_state` | `"active"` at issuance (see ADR-052 for revocation) |

## 2. Signed bytes and signature verification

The signature covers **the canonical JSON encoding of the payload** — not a wire
transcript — so a provider that received the grant as JSON can re-serialize and
verify. Canonical form (normative, `conformance/vectors/` pins it):

* UTF-8; object keys sorted lexicographically by code point
* no insignificant whitespace (separators `,` and `:`)
* non-ASCII emitted literally, not escaped
* absent optional fields encode as JSON `null`, never omitted

A provider MUST verify the Ed25519 signature over those exact bytes against a
**configured trust root**: the issuer's public key, obtained out of band. The trust
root's key id MUST equal the payload's `issuer_key_id`; a grant naming an issuer the
trust root is not MUST be distinguished (`unknown_issuer`) from a broken signature
(`signature_mismatch`) — key rotation (ADR-051) makes the difference operational.

**A provider with no trust root configured MUST deny every redemption**
(`missing_trust_root`). Fail closed is the default, not an error path.

## 3. Time

Validity is judged against a **caller-supplied instant** — the provider decides what
"now" means at its own request boundary; the verify path itself never reads a clock.
Window semantics are half-open, identical to the Kernel's authority windows:

```
not_before <= t < not_after        (null bound = open on that side)
```

Before `not_before` → `not_yet_valid`. At or after `not_after` → `expired`.

## 4. Scope binding

A verified grant authorizes **one specific action**, not a class of them. At
redemption the provider MUST bind:

1. `provider_id` equals the provider's own configured id → else `provider_mismatch`.
2. The requested operation is in `permitted_operations` → else
   `operation_not_permitted`. (ToolConnect maps a tool invocation to `tool.invoke`.)
3. `requesting_principal_id` equals the presenting principal → else
   `principal_mismatch`.
4. `argument_constraints` binds the call:
   * `argument_constraints["tool"]` MUST be present and MUST equal the tool being
     invoked — a grant that does not name this tool is not a grant for it;
   * `argument_constraints["source"]`, when the issuer constrained it, MUST equal
     the source the tool is invoked through;
   * every other constraint key MUST equal the corresponding argument value by exact
     JSON equality.
   A violated constraint is `scope_mismatch` (tool/source) or `args_mismatch`
   (argument values).

Anything the issuer did not constrain, the provider's own policy still governs —
a grant is a ceiling, never an escalation of the provider's own authorization rules.

## 5. One use

A grant redeems **exactly once**, atomically. The provider MUST enforce this in its
own store under the same transaction discipline it uses for any other
mutation-plus-audit pair: the one-use claim and the enforcement record commit
together or not at all. A second presentation of the same `grant_id` denies with
`already_redeemed` — and that denial is itself recorded (§6). A redemption attempt
that fails verification or scope binding does NOT consume the grant; a corrected
retry may succeed.

## 6. The Provider Enforcement Record

Every redemption attempt — success or denial — MUST leave a durable, auditable
**Provider Enforcement Record** containing at least:

```
grant_id, decision_record_id, correlation_id, issuer_key_id,
provider_id, principal_id, operation/tool identity,
args_hash          (canonical-JSON SHA-256 of the presented arguments —
                    never the raw arguments),
verified           (did cryptographic verification pass),
failure_codes      (stable machine-readable codes, empty on success),
outcome            ("redeemed" | "denied:<reason>"),
verification_at    (the instant the window was judged against),
redeemed_at        (null on denial)
```

In ToolConnect this record is an entry on the provider's hash-chained audit log
(kind `provider_enforcement`), written in the same SQLite transaction as the one-use
claim (ADR 0002 §4 over there; the same doctrine as ADR-024 here). The record is the
evidence that enforcement happened at the point of effect — it is what links the
governance Decision Record to what the provider actually did, closing the vertical
slice of ADR-048: 1 Work Request → 1 Decision Record → 1 signed grant → 1 redemption
→ 1 Provider Enforcement Record.

## 7. Interop discipline

Providers do NOT import `connect_governance` or `connect_governance_grants`. They
interoperate through this artifact. Byte-compatibility is proven against the
conformance vectors in `conformance/grant-vectors/` (gv-001 … gv-005): any provider
whose verifier agrees with those vectors — including the tamper, not-yet-valid,
expired, and key-rotation cases — is conformant. ToolConnect's vendored verifier is
the reference consumer; its contract test copies these vectors verbatim and fails if
this contract ever changes silently.

## 8. Failure codes (stable vocabulary)

`malformed_grant` · `unsupported_scheme` · `unsupported_format` ·
`missing_trust_root` · `unknown_issuer` · `key_id_mismatch` · `signature_mismatch` ·
`not_yet_valid` · `expired` · `provider_mismatch` · `operation_not_permitted` ·
`principal_mismatch` · `scope_mismatch` · `args_mismatch` · `already_redeemed`

Every one of them is a **deny**. There is no warn-and-continue anywhere in this
contract.

## 9. What this contract deliberately does not do

* **Revocation propagation** — decided in ADR-052: short validity windows are the
  revocation mechanism for the slice; a revocation-list format is defined there and
  distribution is deferred to R7. A redeemer honors the window; it does not poll a
  revocation feed.
* **Delegation depth enforcement at the provider** — carried on the payload as
  evidence; enforcement is the governance plane's job at issuance time.
* **Budgets** — `budget_limit_usd` is signed evidence the provider may record; spend
  accounting across providers is out of scope for the slice.
