# ADR 0002 — Matching must be deterministic and explainable

- **Status:** accepted
- **Date:** 2026-01

## Context

Candidate ranking decides who gets seen. The dominant approach — opaque scoring, increasingly
embedding-based — produces rankings that nobody can audit, that candidates cannot appeal, and
that are difficult to test. Regulation is also moving: automated decisions affecting
employment increasingly carry a right to an explanation.

An embedding-similarity ranker would have been faster to build and would demo well.

## Decision

`matchProfileToRole` is a pure function of the profile and the role requirements. It returns
a score **and** a per-requirement explanation: met, below level, or missing; required or
optional; verified or self-declared.

Model-assisted features are additive. They may draft a profile, prepare someone for an
interview or summarize a portfolio, and every such output is labelled. They do not decide
eligibility, and they do not silently reorder candidates.

## Consequences

**Good.** Ranking is unit-testable, reproducible, and explainable to the person it affects.
A candidate can be told exactly what was missing, which turns a rejection into direction.

**Cost.** Purely semantic matches are missed — a profile saying "Golang" against a requirement
for `go` will not match unless the skill taxonomy relates them. That is a taxonomy problem,
and we prefer to fix it there, where the fix is inspectable, rather than in an opaque model.

**When to revisit.** Model-assisted *candidate suggestion* is acceptable as a separate,
clearly labelled surface — never as a silent modifier of this score.
