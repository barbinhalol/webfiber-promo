# Architecture

## Shape

OpenCareer is a **modular monolith**: one deployable unit, with hard internal boundaries.
Small teams pay the cost of microservices long before they get the benefit, and a single
process is far easier for a university or a small agency to self-host. The module boundaries
are drawn where a future split would happen, so that split stays cheap.

```
                 ┌──────────────────────────────┐
   HTTP client → │  @opencareer/api             │
                 │  ┌────────────────────────┐  │
                 │  │ routes/  (transport)   │  │  Fastify, request validation,
                 │  └───────────┬────────────┘  │  status codes — no domain rules
                 │              │               │
                 │  ┌───────────▼────────────┐  │
                 │  │ repositories/ (ports)  │  │  ProfileRepository interface
                 │  └───────────┬────────────┘  │
                 │       in-memory │ postgres    │  adapters, swappable
                 └───────────────┬──────────────┘
                                 │
                 ┌───────────────▼──────────────┐
                 │  @opencareer/core            │  OPP schema, completeness,
                 │  pure domain, zero I/O       │  explainable matching
                 └──────────────────────────────┘
```

## Layers

**`@opencareer/core` — the domain.** The profile format and the scoring rules. No database,
no HTTP, no clock it does not receive. This is what makes the rules testable in milliseconds
and reusable outside this server: a validator, a CLI or another implementation of OPP can
depend on `core` alone.

**`@opencareer/api` — transport and storage.** Routes translate HTTP into domain calls and
domain results into status codes. They hold no business rules. Storage sits behind the
`ProfileRepository` port, so swapping in-memory for Postgres touches one file and no route.

## Decisions that shape everything

### The profile is a document, not rows

An OPP profile is a self-contained document that validates on its own. That makes export,
import and federation between instances a matter of moving JSON, not reconstructing a schema
from foreign keys. Storage may normalize internally; the contract at the edge stays the
document.

### Ranking must be explainable

`matchProfileToRole` returns a per-requirement explanation alongside the score. This is a
design constraint, not a feature: a system that filters people out owes them a reason. It
also means the ranking can be unit-tested, which an embedding-similarity black box cannot be.

Model-assisted features (roadmap v0.5) layer on top — drafting, summarizing, preparing — and
are always labelled. They never become the silent arbiter of eligibility.

### Validation happens once, at the boundary

Every write parses through the Zod schema in `core`. Inside the domain, a `Profile` is
already valid, so no function re-checks its inputs defensively. Invalid input never reaches
storage.

### Verification is evidence, not a badge

A skill carries a list of verification records rather than a boolean. That preserves *who*
attested to what, and lets a record stay meaningful after the profile is exported to another
instance (signed records are roadmap v0.4).

## Testing strategy

- **Domain tests** cover the rules directly — scoring boundaries, partial credit, eligibility.
- **API tests** run the real Fastify instance through `app.inject()`, with the in-memory
  adapter. No network, no database, full request/response coverage.
- Any new storage adapter must pass the same contract tests as the in-memory one.

## Technology choices

| Choice | Why |
|---|---|
| TypeScript, strict | The profile format is the product; types keep it honest |
| Fastify | Fast, small, first-class `inject()` testing, no decorator magic |
| Zod | One schema definition serving validation, types and documentation |
| Vitest | Fast enough that contributors actually run the suite |
| PostgreSQL (v0.2) | Boring, well understood, self-hostable anywhere |
