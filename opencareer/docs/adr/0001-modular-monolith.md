# ADR 0001 — Start as a modular monolith

- **Status:** accepted
- **Date:** 2026-01

## Context

OpenCareer needs to be operable by small teams — a university department, a small agency, a
handful of volunteers — and developed by contributors who can only give a few hours. A
service-per-domain architecture would add deployment topology, inter-service contracts and
distributed debugging before there is a single user.

## Decision

Ship one deployable process with enforced internal boundaries:

- `@opencareer/core` holds the domain and performs no I/O.
- `@opencareer/api` holds transport and storage, and depends on `core` — never the reverse.
- Storage sits behind the `ProfileRepository` port.

## Consequences

**Good.** One process to run, one log stream to read, tests that execute in under a second,
and a contributor can hold the whole system in their head.

**Cost.** The whole application scales as a unit, and the boundaries are conventions enforced
by review and by package dependencies rather than by the network.

**When to revisit.** If media transcoding or matching develops resource needs that differ
sharply from the API, extract that module first — the port boundaries mark where to cut.
