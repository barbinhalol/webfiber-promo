# Roadmap

The roadmap is a statement of intent, not a promise of dates. Items move when contributors
pick them up. Anything marked **help wanted** is a good place to start.

## Shipped — v0.1 (current)

- Open Professional Profile (OPP) v0.1 schema: identity, headline, video introduction,
  portfolio, skills with proficiency and verification records, work history
- Deterministic, explainable role matching with partial credit and a verification bonus
- Profile completeness scoring with weighted, ordered suggestions
- HTTP API: profile CRUD, availability filtering, portable export, completeness, matching
- In-memory storage behind a repository port
- 24 unit and integration tests, strict TypeScript, CI on every push

## v0.2 — Persistence and identity

- [ ] PostgreSQL adapter behind the existing `ProfileRepository` port (**help wanted**)
- [ ] Database migrations and a seed dataset
- [ ] Authentication: email link and OAuth, with sessions scoped to a profile
- [ ] Authorization: only the owner may write their profile; public read is opt-in per field
- [ ] Rate limiting and structured audit logging

## v0.3 — Web client

- [ ] Public profile pages, server-rendered and indexable
- [ ] Profile editor with inline completeness guidance
- [ ] Video introduction recording and upload, with transcoding
- [ ] Automatic captions and transcripts — accessibility is a requirement, not an add-on
- [ ] Full keyboard navigation and WCAG 2.2 AA conformance (**help wanted**)

## v0.4 — Roles and verification

- [ ] Role postings with structured requirements
- [ ] Ranked candidate lists that always ship their explanation
- [ ] Employer verification of a work-history record
- [ ] Skill assessments and third-party credential import
- [ ] Signed verification records so a claim survives export to another instance

## v0.5 — Model-assisted features

Every feature here is additive and auditable. A model may draft, suggest or summarize; it
does not decide eligibility on its own, and every model-assisted output is labelled as such.

- [ ] Profile writing assistance — turn a rough description into a structured profile
- [ ] Interview preparation grounded in the actual role requirements
- [ ] Skill-gap analysis against a target role, with learning suggestions
- [ ] Bias review of role postings before they are published

## v1.0 — Ecosystem

- [ ] OPP v1.0, with a conformance test suite any implementation can run
- [ ] Public REST and webhook API with versioning guarantees
- [ ] Import and export adapters for common HR systems
- [ ] Integration guide for educational institutions
- [ ] Reference deployment: Docker Compose and a Helm chart

## Explicit non-goals

- **No dark patterns.** No engagement-maximizing feed, no artificial urgency, no pay-to-be-seen
  ranking. Visibility follows the profile, not the wallet.
- **No selling personal data.** Ever, under any funding model.
- **No opaque automated rejection.** If a system filters a person out, the person can see why.
