# Open Professional Profile (OPP) v0.1

OPP is the portable document at the centre of OpenCareer. A profile validates on its own,
travels as a single JSON file, and can be imported by any conformant instance.

The normative definition is [`packages/core/src/profile.ts`](../packages/core/src/profile.ts).
This page explains the intent behind it.

## Example

```json
{
  "oppVersion": "0.1.0",
  "id": "prf_1",
  "handle": "ana-souza",
  "fullName": "Ana Souza",
  "headline": "Backend engineer focused on distributed systems",
  "bio": "Ten years building payment and identity systems across Latin America.",
  "location": "Rio de Janeiro, Brazil",
  "languages": ["pt-BR", "en"],
  "videoIntro": {
    "kind": "video",
    "url": "https://cdn.example.com/ana-intro.mp4",
    "title": "Who I am and what I build"
  },
  "portfolio": [
    { "kind": "link", "url": "https://github.com/ana", "title": "Open-source work" }
  ],
  "skills": [
    {
      "id": "go",
      "name": "Go",
      "proficiency": "expert",
      "yearsOfExperience": 8,
      "verifications": ["assessment:go-2025"]
    }
  ],
  "experiences": [
    {
      "id": "exp_1",
      "organization": "Acme Payments",
      "title": "Staff Engineer",
      "startDate": "2021-02",
      "summary": "Led the migration of the ledger to an event-sourced design.",
      "skillIds": ["go"],
      "verified": true
    }
  ],
  "openToWork": true,
  "updatedAt": "2026-01-15T10:00:00.000Z"
}
```

## Fields

| Field | Type | Notes |
|---|---|---|
| `oppVersion` | string | Format version. Consumers must reject versions they do not understand. |
| `id` | string | Server-assigned. Stable within an instance, not across instances. |
| `handle` | string | Lowercase, URL-safe, 3–39 characters. The public address of the profile. |
| `fullName` | string | As the person chooses to be named. No structure imposed. |
| `headline` | string | ≤160 characters. |
| `bio` | string? | ≤4000 characters. |
| `location` | string? | Free text — deliberately not a normalized geography. |
| `languages` | string[] | BCP-47 tags recommended. |
| `videoIntro` | media? | The resume replacement: a short self-recorded introduction. |
| `portfolio` | media[] | Work worth looking at: `video`, `image`, `document` or `link`. |
| `skills` | skill[] | Declared capability plus the evidence behind it. |
| `experiences` | experience[] | Work history. |
| `openToWork` | boolean | Availability signal, controlled by the person. |
| `updatedAt` | string | ISO 8601 timestamp, server-assigned. |

### Skill

`proficiency` is one of `beginner`, `intermediate`, `advanced`, `expert` — four levels,
because finer scales invite false precision that nobody calibrates consistently.

`verifications` is a list of record identifiers, not a boolean, so the *source* of trust
survives: `assessment:go-2025`, `employer:acme`, `credential:university-x`. Signed
verification records are roadmap v0.4.

`id` is a taxonomy identifier (`esco:1234`, `opencareer:typescript`) so that skills can be
matched across profiles without string comparison of display names.

### Experience

`startDate` and `endDate` accept `YYYY-MM` or `YYYY-MM-DD`. Month precision is the default
because people rarely remember days, and demanding false precision produces false data. An
absent `endDate` means the position is current. `verified` is set only when an employer or an
accredited partner confirms the record — never by the profile owner.

## Design rules

**Everything optional except identity.** A profile with a handle, a name and a headline is
valid. Completeness is guidance (`GET /v1/profiles/:handle/completeness`), never a gate.

**No demographic fields.** Age, gender, marital status, photographs of the person and
nationality are not part of the format. They are not needed to evaluate work, and their
presence invites discrimination. This is a deliberate omission, and a pull request adding them
will be declined.

**Server-owned fields are not writable.** `id`, `updatedAt` and `oppVersion` are stripped from
input (`profileInputSchema`) and assigned by the server.

## Versioning

`oppVersion` follows semantic versioning. Additive optional fields are a minor bump; removing
or narrowing a field is a major bump and requires a migration note. Before v1.0 the format may
still change — that is what pre-alpha means.
