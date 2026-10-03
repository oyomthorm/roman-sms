# Roman SMS documentation

Everything a developer or operator needs to know about the platform.

## Reading order for a new contributor

1. **`ARCHITECTURE.md`** — the shape of the system in one page
2. **`DECISIONS.md`** — why it is built this way (read the wallet ADR carefully)
3. **`RUNBOOK.md`** — what to do when something breaks
4. **`SCOPE.md`** — what is in v1 and, more importantly, what is not

## Index

| File | Purpose | Update when |
|---|---|---|
| `ARCHITECTURE.md` | Layers, request flow, data model | Design changes |
| `DECISIONS.md` | ADRs — one page per significant decision | A decision is made |
| `SCOPE.md` | v1 in / v1 out / never | Scope changes |
| `BACKLOG.md` | Parked features with requester and cost | A feature is deferred or promoted |
| `CHANGELOG.md` | What shipped, when, in what version | Every release |
| `RUNBOOK.md` | On-call procedures and incident response | A procedure changes |
| `ONBOARDING.md` | How to bring on a new associate | The onboarding flow changes |
| `PERMISSIONS.md` | Role matrix and enforcement rules | A role or rule changes |
| `PRICING.md` | Internal pricing strategy (not shared with clients) | Pricing changes |
| `EGOSMS_NOTES.md` | Pahappa API quirks, constraints, gotchas | API behaviour changes |
| `WEBHOOK.md` | Delivery webhook contract and testing | Webhook shape changes |
| `DEPLOY.md` | Full deployment procedure | The deploy process changes |

## Rules

- If a decision matters and could be argued the other way six months from
  now, write an ADR.
- If a procedure is not written down, it is not a procedure.
- If a scope boundary is not in `SCOPE.md`, it will be crossed.
- Every release gets a `CHANGELOG.md` entry before it is tagged.