# Contributing to OpenCareer

Thank you for considering it. OpenCareer is pre-alpha, which means early contributors shape
the project rather than just maintain it.

You do not have to be a developer. Recruiters, career counsellors, accessibility specialists
and people who have recently job-hunted all see problems the code cannot. Issues describing
what is broken about hiring are as valuable as pull requests.

## Getting set up

Node.js 20 or newer.

```bash
git clone https://github.com/OWNER/opencareer.git
cd opencareer
npm install
npm test        # should be green before you change anything
npm run dev     # API on http://localhost:3000
```

Useful commands:

| Command | What it does |
|---|---|
| `npm test` | Run the full suite once |
| `npm run test:watch` | Re-run affected tests as you edit |
| `npm run typecheck` | Strict TypeScript across all packages |
| `npm run build` | Compile every package |

## Where things live

- `packages/core` — the profile format and the scoring rules. **No I/O here.** If your change
  needs a database, a clock or the network, it belongs in `api`.
- `packages/api` — HTTP transport and storage adapters. Routes translate and validate; they
  hold no business rules.
- `docs/` — architecture, data model, API reference, ADRs.

## Making a change

1. **Open an issue first** for anything larger than a bug fix or a typo. It saves you from
   building something that conflicts with a decision recorded in `docs/adr/`.
2. Branch from `main`.
3. Write the test alongside the change. New behaviour without a test will be asked for one.
4. Run `npm test` and `npm run typecheck` before pushing.
5. Open the pull request. Describe what changes for the person using the platform, not just
   what changed in the code.

Small, focused pull requests get reviewed quickly. A 2000-line PR touching four concerns
will sit.

## Code style

- Strict TypeScript. No `any`, no non-null assertions in production code.
- Validate at the boundary, then trust the type. Domain functions do not re-check their inputs.
- Comments explain *why*, not *what*. If the code needs a comment to say what it does, rename
  things instead.
- Follow the surrounding code. Consistency beats personal preference.

## Things that will be declined

These are not judgements about you — they are project constraints recorded in the docs:

- **Demographic fields on the profile** (age, gender, marital status, personal photographs,
  nationality). See [docs/data-model.md](./docs/data-model.md#design-rules).
- **Ranking that cannot explain itself.** Any change to matching must keep the per-requirement
  explanation intact. See [ADR 0002](./docs/adr/0002-explainable-matching.md).
- **Engagement mechanics** — streaks, artificial urgency, pay-to-be-seen ranking. See the
  non-goals in [ROADMAP.md](./ROADMAP.md).
- **Selling or brokering personal data**, under any funding model.

If you think one of these constraints is wrong, open an issue and argue the case. They are
decisions, not commandments — but they change through discussion, not through a pull request.

## Reporting security issues

Do not open a public issue. See [SECURITY.md](./SECURITY.md).

## Licensing

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](./LICENSE).
