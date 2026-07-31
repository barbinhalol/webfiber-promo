# Security policy

## Current status

OpenCareer is **pre-alpha**. Authentication and authorization are not implemented (roadmap
v0.2). Any instance reachable from the network can be read and modified by anyone who reaches
it. Do not run a public instance and do not store real personal data in one yet.

## Supported versions

Until v1.0, only the `main` branch receives security fixes.

## Reporting a vulnerability

Please report privately, not in a public issue.

1. Open a [private security advisory](https://github.com/OWNER/opencareer/security/advisories/new)
   on GitHub, or
2. email the maintainers (see the address in the repository profile).

Include what you found, how to reproduce it, and what an attacker could do with it. A proof of
concept helps enormously.

**What to expect:** an acknowledgement within 5 days, an assessment within 14 days, and credit
in the advisory unless you prefer otherwise. We will let you know when a fix ships.

Please do not test against instances you do not operate, and do not access, modify or retain
data belonging to other people while investigating.

## Scope

In scope: this repository's code, its dependencies as configured here, and the documented
deployment guidance.

Out of scope for now: the absence of authentication and rate limiting, which is known,
documented above, and tracked in [ROADMAP.md](./ROADMAP.md).

## Handling personal data

OpenCareer holds career histories — sensitive data with real consequences for the people it
describes. When reporting or fixing an issue, treat any profile data you encounter as
confidential and delete anything you copied once the report is resolved.
