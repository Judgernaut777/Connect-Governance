# Canonical corpus pointer

**The authoritative architecture for Connect and GAS does not live in this repository.**

It lives in the Google Drive folder **“Connect Architecture”**
(`10cwcLGv1qp1wkMGVOfLC23gucbGImNrL`), owned by judgems77@gmail.com.

Per Documentation Constitution §2.2, documentation is a primary product artifact, not a
retrospective description of code. Code conforms to the corpus; the corpus does not describe
the code after the fact.

## The corpus

| # | Document | Answers |
|---|---|---|
| 00 | Documentation Constitution | How is the corpus itself governed? |
| 01 | GAS Methodology | How should organizations govern autonomous work? |
| 02 | Connect Thesis | Why does Connect exist? |
| 03 | Connect Model | How does Connect see an organization? |
| 04 | Connect Constitution | What must always remain true? |
| 05 | Connect Reference Architecture **v0.2** | How can Connect be built correctly? |
| 06 | Connect Lexicon | What does each canonical term mean? |
| 07 | Connect Decision Log (ADR-001…033) | Why was this decided? |
| 07a | Decision Log Addendum v0.2 (ADR-034…048) | Decisions from the 2026-08-03 review |
| 08 | Architecture Discovery Log | How did the model develop? |
| 09 | Architecture Session Transcripts | Historical source material |
| 10 | Connect Chronicle | Narrative history |

## Precedence when documents conflict

Documentation Constitution §4:

1. Connect Constitution
2. Canonical Lexicon (for term meaning)
3. Connect Model
4. Connect Reference Architecture
5. Product implementation and operational documentation ← *this repository*

The Decision Log explains **why** authoritative choices were made. It does not override the
current Constitution.

## Rules this repository inherits

- **The Decision Log is append-only** (§3.7). Supersede; never silently rewrite.
- **Maturity labels** (§6): Draft → Candidate → Ratified → Superseded. The corpus is
  currently **Draft**.
- **Every architecture session ends with a capture record** (§8).
- **Every material change** must identify the affected artifact, the reason, the concepts and
  definitions affected, the constitutional principles involved, compatibility consequences,
  required updates to dependent documents, and the Decision Log entry (§7).

## Local ADRs

ADRs under [docs/adr/](docs/adr/) record implementation-level decisions made in this
repository. Any decision that is architectural or constitutional must also be reflected in the
canonical Decision Log — no accepted architectural decision may exist only in conversation, or
only in a code repository (§2.1).
