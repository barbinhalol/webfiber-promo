# OpenCareer

**An open-source platform for dynamic professional profiles and transparent hiring.**

[![CI](https://github.com/OWNER/opencareer/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/opencareer/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange.svg)](./ROADMAP.md)

> **Project status: pre-alpha.** The profile format, the domain model and the HTTP API are
> implemented and tested. Persistence, authentication and the web client are in progress —
> see [ROADMAP.md](./ROADMAP.md). We are looking for contributors.

---

## The problem

Hiring still runs on a document invented in the 1480s. A resume is a static, one-page,
self-declared summary that:

- **loses everything that is not text** — how someone explains their work, what they built,
  how they think;
- **cannot be verified** — a claim of "5 years of Go" carries exactly as much weight as the
  truth, so employers discount every claim equally;
- **is locked inside whichever platform you typed it into** — your professional history is
  your data, but exporting it in a form another system understands is usually impossible;
- **stops mattering the moment you are hired**, even though most career growth happens after
  that point.

Meanwhile the tooling on the other side of the table has moved to opaque, proprietary
ranking. Candidates are filtered by systems they cannot inspect and cannot appeal.

## What OpenCareer is

OpenCareer replaces the static resume with the **Open Professional Profile (OPP)** — a
portable, verifiable, media-rich document that the person owns:

| | Static resume | OpenCareer profile |
|---|---|---|
| Format | PDF / text | Structured JSON + video + portfolio |
| Trust | Self-declared | Self-declared **plus** verifiable records |
| Ownership | Locked in a platform | Exportable, self-hostable |
| Ranking | Opaque, vendor-controlled | Deterministic and **explainable** |
| Lifecycle | Ends at hiring | Continues through the career |

Three commitments hold the project together:

1. **The profile is portable.** `GET /v1/profiles/:handle/export` returns a complete OPP
   document. Any conformant instance can import it. No lock-in, by construction.
2. **Ranking is explainable.** Every match returns *why* — which requirement was met, which
   was below level, which was missing, and whether the evidence was verified. Model-assisted
   features build on top of that score; they never silently replace it.
3. **Anyone can run it.** The whole stack is Apache-2.0 and self-hostable. A university, a
   public employment agency or a co-op should be able to operate its own instance.

## Quick start

Requires Node.js 20 or newer.

```bash
git clone https://github.com/OWNER/opencareer.git
cd opencareer
npm install
npm test          # 24 tests
npm run dev       # API on http://localhost:3000
```

Create a profile and inspect how it scores:

```bash
curl -X POST http://localhost:3000/v1/profiles \
  -H 'content-type: application/json' \
  -d '{
    "handle": "ana-souza",
    "fullName": "Ana Souza",
    "headline": "Backend engineer focused on distributed systems",
    "openToWork": true,
    "skills": [
      { "id": "go", "name": "Go", "proficiency": "expert", "verifications": ["assessment:go-2025"] }
    ]
  }'

# Why does this candidate match the role?
curl -X POST http://localhost:3000/v1/profiles/ana-souza/match \
  -H 'content-type: application/json' \
  -d '{ "requirements": [
        { "skillId": "go", "minimumProficiency": "advanced", "required": true },
        { "skillId": "kubernetes", "minimumProficiency": "intermediate", "required": false }
      ] }'
```

```jsonc
{
  "score": 75,
  "eligible": true,
  "explanations": [
    { "skillId": "go", "status": "met", "required": true, "verified": true },
    { "skillId": "kubernetes", "status": "missing", "required": false, "verified": false }
  ]
}
```

The full endpoint reference is in [docs/api.md](./docs/api.md).

## Repository layout

```
opencareer/
├── packages/
│   ├── core/     # Domain model: OPP schema, completeness scoring, explainable matching
│   └── api/      # Fastify HTTP API, storage ports and adapters
├── docs/         # Architecture, data model, API reference, self-hosting, ADRs
└── ROADMAP.md    # What is built, what is next
```

`@opencareer/core` has no I/O and no framework dependency: it is the profile format plus the
scoring rules, usable on its own by anyone who wants to read or emit OPP documents.

## Documentation

- [Architecture](./docs/architecture.md) — how the pieces fit and why
- [Data model](./docs/data-model.md) — the Open Professional Profile format
- [API reference](./docs/api.md)
- [Self-hosting](./docs/self-hosting.md)
- [Architecture decision records](./docs/adr/)
- [Roadmap](./ROADMAP.md)

## Contributing

Contributions are welcome, including from people who are not looking for a job themselves —
recruiters, educators and accessibility specialists all shape this problem. Start with
[CONTRIBUTING.md](./CONTRIBUTING.md) and the issues labelled `good first issue`.

## License

[Apache License 2.0](./LICENSE) — permissive, with an explicit patent grant, so companies and
public institutions can adopt and extend the platform without legal friction.
