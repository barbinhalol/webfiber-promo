# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Next up: the PostgreSQL adapter and authentication — see [ROADMAP.md](./ROADMAP.md).

## [0.1.0] — 2026-01

Initial public release. Pre-alpha: the format may still change before v1.0.

### Added

- Open Professional Profile (OPP) v0.1 format — identity, headline, video introduction,
  portfolio, skills with proficiency and verification records, and work history
- Deterministic, explainable role matching with partial credit for below-level skills and a
  scoring bonus for verified evidence
- Weighted profile completeness scoring with ordered suggestions
- HTTP API — profile CRUD, availability filtering, portable OPP export, completeness and
  matching endpoints
- In-memory storage adapter behind the `ProfileRepository` port
- Target PostgreSQL schema for the persistence adapter
- Architecture, data model, API, self-hosting documentation and the first two ADRs
- CI running typecheck, tests and build on Node 20 and 22
