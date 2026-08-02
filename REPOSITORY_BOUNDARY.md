# Repository boundary

What Connect-Governance owns, what it does not, and where the line is drawn.
Authoritative source: **ADR-035** (Connect-Governance ↔ AgentConnect ownership boundary).

## This repository owns

- Organizations, Personal Spaces, Workspaces
- Persons and governed identities
- Agents **as governed organizational actors** (not as runtime processes)
- Roles, Role Assignments, and authority relationships
- Organizational Policy and Policy versions
- Work Requests and Work Request revisions
- Governed state Transitions
- The **Decision Kernel** and canonical authorization Decisions
- **Connect Decision Records**
- **Execution-grant issuance** (signing, binding, revocation state)
- Governance audit history
- Genesis / deployment trust-root establishment

## This repository does NOT own

| Concern | Owner |
|---|---|
| Tasks, subtasks, plans, decomposition | AgentConnect |
| Workers, runs, retries, checkpoints | AgentConnect |
| Execution coordination and runtime behaviour | AgentConnect |
| Tool authorization at the point of effect | ToolConnect |
| Compute placement and admission | ComputeConnect |
| Trusted memory and its promotion gate | BrainConnect |
| Authentication (passwords, MFA, SAML, OAuth, LDAP) | External identity providers |
| Planning, reasoning, orchestration | Harnesses |

AgentConnect is **not being rewritten and not being discarded**. Its existing approvals,
delegation envelopes, budgets, privacy controls, and audit are to be **reused and integrated**,
not rebuilt. Per-capability disposition is tracked as OD-012.

## The load-bearing separations

**Authorization is not enforcement.** Connect-Governance decides whether an organizational
commitment may be made and issues a grant. It does not sit on the data path of the resulting
actions. Enforcement happens at the provider, at the point of effect (ADR-038).

**Authorizing a Work Request does not authorize every action inside it.** Materially effectful
actions must be enforced at the resource boundary against a grant bound to their material
parameters. Approval to call a tool does not authorize every possible set of arguments.

**The Kernel decides; it does not execute.** No planning, orchestration, scheduling, or direct
state mutation. See ADR-025.

**Structure does not imply authority.** Containment, provenance, and hierarchy never create
authority. Authority derives from explicit graph relationships and is constrained by Policy.

## The three record kinds (ADR-037)

Linkable, never interchangeable:

| Record | Answers | Produced by |
|---|---|---|
| **Connect Decision Record** | Was it authorized? | Connect-Governance |
| **Provider Enforcement Record** | Was it enforced at the point of effect? | ToolConnect / ComputeConnect / BrainConnect / approved providers |
| **Execution Record** | What actually ran? | AgentConnect or another runtime |

An audit trail that cannot distinguish *authorized but never enforced* from *enforced* is not
an audit trail.

## Vocabulary boundary (ADR-036)

The Lexicon governs this repository's APIs, cross-product contracts, and shared ecosystem
documentation. Peer products keep their product-local vocabulary where an explicit mapping
exists:

- AgentConnect **task / subtask** → internal execution decomposition; **not** a Work Request
- AgentConnect **run** → approximately an **Execution**
- AgentConnect **worker** → **not** automatically a Principal or a governed Agent
