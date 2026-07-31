# API reference

Base URL in development: `http://localhost:3000`. All request and response bodies are JSON.

> Authentication is not implemented yet (roadmap v0.2). Do not expose an instance publicly
> until it is: every endpoint below is currently unauthenticated.

## Conventions

- Validation failures return `400` with `{ "error": "...", "details": { fieldErrors, formErrors } }`.
- Unknown profiles return `404` with `{ "error": "profile_not_found" }`.
- Handle collisions return `409` with `{ "error": "handle_taken" }`.

## Health

### `GET /healthz`

```json
{ "status": "ok", "oppVersion": "0.1.0" }
```

## Profiles

### `GET /v1/profiles`

Lists profiles, most recently updated first.

| Query | Type | Notes |
|---|---|---|
| `openToWork` | `true` \| `false` | Optional availability filter |

```json
{ "data": [ { "handle": "ana-souza", "...": "..." } ] }
```

### `POST /v1/profiles`

Creates a profile. The body is an OPP document without the server-owned fields (`id`,
`updatedAt`, `oppVersion`). Returns `201` with a `Location` header.

### `GET /v1/profiles/:handle`

Returns the full OPP document.

### `PUT /v1/profiles/:handle`

Full replacement. The profile keeps its `id`; `updatedAt` is refreshed. Changing `handle` in
the body renames the profile, and fails with `409` if the new handle is taken.

### `DELETE /v1/profiles/:handle`

Returns `204` on success, `404` if the profile does not exist.

## Portability

### `GET /v1/profiles/:handle/export`

Returns the profile as a downloadable OPP document
(`content-disposition: attachment; filename="<handle>.opp.json"`). This endpoint is the
guarantee against lock-in: the file it returns is complete and re-importable elsewhere.

## Guidance and matching

### `GET /v1/profiles/:handle/completeness`

```json
{
  "score": 35,
  "checks": [ { "key": "video-intro", "label": "Record a video introduction", "weight": 25, "satisfied": true } ],
  "suggestions": [ { "key": "skills", "label": "List at least five skills", "weight": 15, "satisfied": false } ]
}
```

`suggestions` contains the unsatisfied checks, heaviest first — the ordered list of what to
do next.

### `POST /v1/profiles/:handle/match`

```json
{
  "requirements": [
    { "skillId": "go", "minimumProficiency": "advanced", "required": true },
    { "skillId": "kubernetes", "minimumProficiency": "intermediate", "required": false }
  ]
}
```

Response:

```json
{
  "score": 75,
  "eligible": true,
  "explanations": [
    { "skillId": "go", "status": "met", "required": true, "verified": true },
    { "skillId": "kubernetes", "status": "missing", "required": false, "verified": false }
  ]
}
```

- `status` is `met`, `below-level` (the skill exists but not at the requested level — half
  credit) or `missing`.
- `eligible` is `false` when any **required** requirement is not fully met.
- A verified skill scores 25% above the same unverified skill.
- Up to 50 requirements per request. An empty requirement list is an open call:
  `{ "score": 0, "eligible": true, "explanations": [] }`.

Scoring is deterministic and depends only on the profile and the requirements — the same input
always produces the same explanation.
