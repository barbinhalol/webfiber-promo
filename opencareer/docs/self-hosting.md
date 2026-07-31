# Self-hosting

Running your own instance is a first-class use case, not an afterthought. A university, a
public employment agency, a co-op or a company should be able to operate OpenCareer on its own
infrastructure, with its own data.

> **Pre-alpha.** The current build stores profiles in memory and has no authentication. It is
> suitable for local development and evaluation only. Durable storage and auth land in v0.2 —
> see [ROADMAP.md](../ROADMAP.md).

## Requirements

- Node.js 20 or newer
- PostgreSQL 15 or newer (from v0.2)

## Running from source

```bash
git clone https://github.com/OWNER/opencareer.git
cd opencareer
npm install
cp .env.example .env
npm test
npm run build
npm start --workspace @opencareer/api
```

The API listens on `PORT` (default `3000`) and `HOST` (default `0.0.0.0`).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `3000` | HTTP port |
| `HOST` | `0.0.0.0` | Bind address |
| `LOG_LEVEL` | `info` | Log verbosity |
| `DATABASE_URL` | unset | Postgres connection string. Unset means the in-memory adapter (development only). |
| `PUBLIC_BASE_URL` | `http://localhost:3000` | Base URL used in emitted documents |

Never commit `.env`. It is listed in `.gitignore`.

## Health checks

`GET /healthz` returns `200` with the running OPP format version. Point your orchestrator's
liveness and readiness probes at it.

## Data ownership

Every profile can be exported at any time:

```bash
curl -O -J http://localhost:3000/v1/profiles/ana-souza/export
```

The resulting `.opp.json` file is complete and importable into any other conformant instance.
If you operate an instance, make sure your users know this endpoint exists — the portability
guarantee is only real if people can use it.

## Before exposing an instance publicly

Wait for v0.2. Until authentication and authorization ship, anyone who can reach the API can
read, modify and delete any profile. If you want to help get there, the Postgres adapter and
the auth layer are both marked **help wanted** in the roadmap.
