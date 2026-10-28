
---

## ADR-019 — Token-authenticated JSON API and Flutter client

**Date:** 2026-10-26 · **Status:** Accepted

**Context.** Associates need to manage their accounts on Android. The web app is cookie/session-based. Adding a separate backend would duplicate business rules.

**Decision.** Add a JSON API at `/api/v1/` on the existing Flask app. Auth is opaque tokens in `api_tokens` presented as `Authorization: Bearer`. Every mutating endpoint requires an `Idempotency-Key` header to prevent double-charging on network retries. The Flutter client uses a live `/campaigns/preview` endpoint to ensure the server remains authoritative for segment arithmetic.

**Consequences.**
- No new business logic. API routes are thin adapters over existing `services/`.
- `org_id` is taken from `current_user`, never from the request.
- `services.create_campaign`, `create_invoice`, and `create_schedule` now accept a `commit=False` kwarg, allowing the API layer to commit the idempotency record and the business action in one transaction.
- Push notifications are deferred (ADR-008 requires event hooks).
- Master console remains desktop-only.

---

---

## ADR-019 â€” Token-authenticated JSON API and Flutter client

**Date:** 2026-10-26 Â· **Status:** Accepted

**Context.** Associates need to manage their accounts and send campaigns on Android. The existing web app is cookie/session-based and serves HTML. Building a separate backend for mobile would duplicate the business rules living in `services/`.

**Decision.** Add a JSON API at `/api/v1/` on the existing Flask app. Auth is handled by opaque tokens stored in the `api_tokens` table and presented as `Authorization: Bearer <token>`. Every mutating endpoint (e.g., creating a campaign) requires an `Idempotency-Key` header. The Flutter client uses a live `/campaigns/preview` endpoint to ensure the server remains authoritative for segment arithmetic.

**Consequences.**
- No new business logic. API routes are thin adapters over existing `services/`.
- `org_id` is taken from `current_user`, never from the request body.
- Service methods (`create_campaign`, `create_invoice`) now accept a `commit=False` kwarg, allowing the API layer to commit the idempotency record and the business action in the same transaction.
- The API is CSRF-exempt, as Bearer tokens are immune to CSRF.
- Push notifications remain deferred (see ADR-008).
- Master console remains desktop-only.
