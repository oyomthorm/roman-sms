# Part 6b — Mobile API reference (`/api/v1/*`)

The mobile JSON surface for the Flutter client. Twelve modules,
CSRF-exempt, Bearer-token authenticated, all business logic delegated
to the same services the web app uses.

If you are looking for the HTML routes, read `06-api-web.md` instead.

## 6b.1 Auth model

**Bearer tokens.** The client logs in via `POST /api/v1/auth/login`
with `{email, password}`, receives `{token, user, org}`. The token is
an opaque string of the form `rsms_<random>`. It is stored **hashed**
in `api_tokens` — the plaintext is shown to the client once and never
again.

**No cookies, no CSRF.** The entire `/api/v1/*` tree is CSRF-exempt,
applied per-child-blueprint in `app/api/v1/__init__.py` via the
`_CHILDREN` list. Every new child blueprint must be added to
`_CHILDREN`; Flask-WTF does not cascade exemption from parent to
child.

**Token expiry** is enforced by the `api_tokens` table, not a JWT
claim. Tokens are opaque; the client cannot inspect expiry from the
token string. The server rejects expired tokens with a 401.

**Auth middleware.** `app/api/v1/utils.py::install_api_auth` reads
the `Authorization: Bearer <token>` header, looks up the hash,
attaches `current_user` to the request, or returns 401. Applied once
to the `/api/v1` blueprint group.

## 6b.2 `org_id` invariants

Every handler derives `org_id` from `current_user.org_id`. **No
request body, query string, or URL path supplies `org_id`.** If a
request appears to accept an org ID, it is a bug — report it.

This is the single most important invariant in the mobile API. The
web app has the same rule; the mobile API has nothing else that
prevents a client from seeing another org's data. A violation is a
security incident.

## 6b.3 Serialization rules

`app/api/v1/serializers.py` defines the shape of every JSON response.
The module exports: `iso`, `user`, `org`, `wallet`, `contact`,
`campaign`, `group`, `paginated`.

**`iso(dt)`** — timestamp serialization. **Emits a naive ISO-8601
string without a `Z` suffix.** The datetime is UTC; the absence of
`Z` is a known issue (backlog). Clients should treat the string as
UTC. This is real: an `iso(2026-11-13T09:00:00)` in a response means
09:00:00 UTC, not local time.

**`Decimal` fields serialize as strings.** `price_ugx`, `rate_ugx`,
`value_ugx` — every monetary field is a string in JSON. Clients parse
with `num.parse()`. The reason is precision: JSON numbers are IEEE-754
floats, and 99999.99 does not round-trip exactly. Strings preserve the
exact decimal.

**List responses use `paginated`.** The convention is
`{"items": [...], "page": N, "per_page": M, "total": T}` — `[VERIFY:
exact pagination envelope from serializers.paginated]`. Single-item
reads return the object directly, not wrapped.

**Field names are snake_case**, matching the model columns. No
camelCase transformation. The Flutter client parses `group_id`, not
`groupId`.

## 6b.4 Auth module — `api/v1/auth.py`

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/v1/auth/login` | `{email, password}` | `{token, user, org}` or 401 |
| POST | `/api/v1/auth/logout` | `{}` (token in header) | `{ok: true}` — invalidates token |
| GET | `/api/v1/auth/me` | (token in header) | `{user, org}` — `[VERIFY: exact shape, includes wallet?]` |
| POST | `/api/v1/auth/signup` | `{...}` — `[VERIFY: exact fields, matches public signup form]` | `{ok: true}` or error |
| PATCH | `/api/v1/auth/profile` | `{name?, ...}` — `[VERIFY: allowed fields]` | `{user}` |
| POST | `/api/v1/auth/password` | `{old_password, new_password}` | `{ok: true}` or error |

**Login failures** return 401 with a generic message — never reveal
whether the email exists. The terminate guard (`is_active_flag=False`)
returns 401 with the same generic message, so a terminated user cannot
distinguish termination from wrong password via the login endpoint.

**Token lifetime** — `[VERIFY from config.py — API_TOKEN_TTL_DAYS or
similar; default expected 30 days]`. There is no refresh-token flow.
When a token expires, the client re-authenticates.

## 6b.5 Dashboard — `api/v1/dashboard.py`

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/api/v1/dashboard` | Bearer | dashboard stats object |

**Known issue: master org users get master-org stats.** A master
user hitting this endpoint sees the master org's numbers, not a
cross-org rollup. Cross-org aggregate is web-only at `/master`.

Expected fields — `[VERIFY from handler api/v1/dashboard.py:index —
expected sent_30d, delivered_30d, failed_30d, trend[], wallet_balance,
days_remaining]`.

## 6b.6 Wallet — `api/v1/wallet.py`

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/api/v1/wallet` | Bearer | `{balance, currency}` — `[VERIFY: exact fields]` |
| GET | `/api/v1/wallet/transactions` | Bearer | paginated list of transactions |

Each transaction — `[VERIFY from serializers — expected id, delta,
balance_after, reason, reference, notes, created_at]`. `delta` and
`balance_after` are integer (credit count), not decimal.

Query params for transactions — `[VERIFY: page, per_page, reason,
date_from, date_to]`.

## 6b.7 Plans — `api/v1/plans.py`

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/api/v1/plans` | Bearer | list of available plans |

Each plan — `[VERIFY: expected id, name, description, price_ugx,
credits, validity_days, max_per_minute, max_per_day]`. `price_ugx` is
a string per §6b.3.

**The list is informational only.** There is no purchase endpoint —
self-service plan purchase is backlog #43. The client should display
plans for reference and instruct users to contact the operator to
buy.

## 6b.8 Campaigns — `api/v1/campaigns.py`

| Method | Path | Auth | Response |
|---|---|---|---|
| POST | `/api/v1/campaigns/preview` | Bearer | `{recipients, segments_per_recipient, total_segments, cost}` |
| GET | `/api/v1/campaigns` | Bearer | paginated campaign list |
| GET | `/api/v1/campaigns/<id>` | Bearer | campaign detail |
| POST | `/api/v1/campaigns` | Bearer + `Idempotency-Key` | created campaign |

**Campaign creation requires an `Idempotency-Key` header.** This is
enforced via `require_idempotency` from `app/api/v1/utils.py`. The
key is checked against `ApiIdempotency` table — a repeated POST with
the same key returns the original response, not a duplicate campaign.
This protects against network retries creating duplicate sends. The
value must be a UUID or high-entropy string; the server does not
validate format, only uniqueness.

Body shape for create — `[VERIFY from handler
api/v1/campaigns.py:create — expected body, target_type (group/district/
all), group_id, district_id, personalized CSV?]`.

Preview endpoint returns the cost estimate. The mobile client uses
this to show "this will cost N credits" before submit. The cost
computation matches the server's `create_campaign` — same segment
arithmetic. If preview and actual diverge, that is a bug.

Campaign detail — `[VERIFY: expected fields — likely id, name, status,
body, recipients_count, sent_count, delivered_count, failed_count,
created_at, completed_at]`.

**Campaign cancel is not implemented in the mobile API.** Web-only.
The client should link to the web app for cancel, or omit the action.

**Schedules are not in the mobile API.** The client can send but not
schedule. Scheduling is web-only.

## 6b.9 Contacts — `api/v1/contacts.py`

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/api/v1/contacts` | Bearer | paginated contacts, filter by `group_id`, `q` |
| POST | `/api/v1/contacts` | Bearer | created contact |
| GET | `/api/v1/contacts/<id>` | Bearer | contact detail |
| PATCH | `/api/v1/contacts/<id>` | Bearer | updated contact |
| DELETE | `/api/v1/contacts/<id>` | Bearer | `{ok: true}` — **hard delete** |
| POST | `/api/v1/contacts/<id>/optout` | Bearer | `{ok: true}` — propagates opt-out |

**DELETE is a hard delete.** No soft-delete, no undo. The row is
gone. The client should confirm before calling.

**`PATCH` supports partial updates** — send only the fields you want
to change. `[VERIFY: which fields are patchable — expected name,
group_id, district_id, notes]`.

Contact shape — `[VERIFY from serializers.contact — expected id, name,
phone, group_id, group_name, district_id, district_name, opted_out,
notes, created_at]`.

Query params — `[VERIFY: page, per_page, group_id, q (search name or
phone), opted_out]`.

## 6b.10 Groups — `api/v1/groups.py`

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/api/v1/groups` | Bearer | paginated groups |
| POST | `/api/v1/groups` | Bearer | created group |
| GET | `/api/v1/groups/<id>` | Bearer | group detail |
| GET | `/api/v1/groups/<id>/contacts` | Bearer | paginated contacts in group |
| PATCH | `/api/v1/groups/<id>` | Bearer | updated group |
| DELETE | `/api/v1/groups/<id>` | Bearer | `{ok: true}` — hard delete |

**`GET /api/v1/groups/<id>` returns `contact_count: null` by design.**
The count is computed on the contacts listing endpoint, not on the
group detail. This is documented behavior, not a bug — the group
detail avoids the count query for performance, and clients that need
the count use `/groups/<id>/contacts` and read `total`.

Group shape — `[VERIFY from serializers.group — expected id, name,
description, contact_count (null on detail), created_at]`.

## 6b.11 Chat — `api/v1/chat.py`

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/api/v1/chat/channels` | Bearer | channel list for current user |
| GET | `/api/v1/chat/channels/<id>/messages` | Bearer | paginated messages |
| POST | `/api/v1/chat/channels/<id>/messages` | Bearer | created message |

Polling is client-driven — the mobile app polls messages on a
schedule. The web app uses 3-second polling; mobile may differ. There
is no push mechanism.

Message shape — `[VERIFY: expected id, sender_id, sender_name, body,
sent_at, is_read]`.

Send body — `[VERIFY: expected {body: "..."}]`.

Read state — the mobile API does not appear to expose a read-state
mutation endpoint (the web app has `ChatReadState`). `[VERIFY: is
read state tracked via the messages GET, or does the mobile client
never mark read?]`.

## 6b.12 Notifications — `api/v1/notifications.py`

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/api/v1/notifications` | Bearer | live-computed notifications |
| POST | `/api/v1/notifications/<key>/dismiss` | Bearer | `{ok: true}` |

Notification shape — `[VERIFY: expected {key, title, body, severity,
action_url?}]`. Same live-computed semantics as web
(`06-api-web.md` §6a.14).

## 6b.13 Error responses

`app/api/v1/utils.py::install_api_errors` installs error handlers
that return JSON for all `/api/v1/*` paths. Consistent envelope:

    {"error": "message", "code": "short_code"}

HTTP status codes:

| Status | Meaning |
|---|---|
| 200 | Success |
| 201 | Created (POST) |
| 400 | Bad request — validation failure |
| 401 | Missing, expired, or invalid token; also login failure |
| 403 | Authenticated but not permitted (rare in mobile — most permission issues surface as 404) |
| 404 | Not found, OR record exists outside user's scope |
| 409 | Conflict — duplicate phone on contact create, idempotency replay with changed payload |
| 422 | Unprocessable — validation error with field detail |
| 429 | Rate limited — `[VERIFY: is rate limiting active on any /api/v1 route?]` |
| 500 | Server error — logged with request ID |

**404 vs 403.** Same rule as web: a record outside the user's scope
returns 404, not 403. Do not infer existence from the distinction.

**Field-level errors** in 422 responses — `[VERIFY: exact shape —
likely {"error": "...", "fields": {"name": ["is required"]}}]`.

## 6b.14 CSRF exemption — `_CHILDREN` list

`app/api/v1/__init__.py` has a `_CHILDREN` list of child blueprints.
Every child must be listed there for CSRF exemption. When adding a
new `/api/v1/*` module:

1. Create the blueprint
2. Register it under `api_v1_bp`
3. Add it to `_CHILDREN`

Missing a `_CHILDREN` entry means the endpoint accepts POST but
rejects it with a 400 CSRF error. This is a common source of "works
in dev, fails in prod" confusion.

## 6b.15 Testing status

**The mobile API has no test coverage as of 0.12.0** (ADR-019).
Promoting `tests/integration/test_mobile_api.py` before the next
feature lands on `/api/v1/` is a backlog item.

Until then, changes to `api/v1/*` should be verified manually — hit
the endpoint, check the response shape matches the client's
expectations, check the serializer fields match. The Flutter app's
health check (backlog: "Flutter mobile app health check — High") will
also exercise this surface.

## 6b.16 Mobile client quirks (from prior sessions)

These are known issues in the Flutter client that affect how the API
is used. They are documented here so a maintainer knows the API's
real-world usage, not just its intended contract:

- **`withOpacity` deprecation** — `contacts_screen.dart:171`,
  `chat_detail_screen.dart:99,134`. Not API-related; UI polish.
- **Router churn** — `routerProvider` recreates GoRouter on every
  auth state change. Client-side. Does not affect server.
- **`_refresh()` uses bare `catch (_)`** — `ContactDetailScreen`
  swallows all refresh errors. API errors are visible in logs but
  invisible in UI.
- **Error handling uses `contains('422')`** — brittle string match on
  status code instead of checking the status directly.
- **Hardcoded dashboard strings** — `dashboard_screen.dart` has
  "Hello, Admin" and "Roman SMS • Verified" hardcoded. The API does
  return the actual user name; the client ignores it.
- **Base URL hardcoded** to `https://romansms.com` in
  `lib/api/client.dart` — must become `--dart-define` before any
  staging deploy (ADR-022).

These are client-side. The API is behaving correctly; the client is
not always using it correctly. Fixing the client is a separate
workstream from the API reference.

## 6b.17 Adding a new mobile endpoint (checklist)

1. New handler in the appropriate `api/v1/<resource>.py`.
2. If it needs auth, ensure `install_api_auth` is applied — this is
   applied at the `api_v1_bp` level, so individual handlers get it
   automatically.
3. If it mutates and is idempotency-sensitive (sends, payments),
   apply `require_idempotency`.
4. Derive `org_id` from `current_user.org_id`. Never from request.
5. Call the same service the web route calls. If there's no service
   for the operation, create one — do not put business logic in the
   API handler.
6. Serialize with the module's serializers. If a new field is needed,
   add it to `serializers.py`, not inline in the handler.
7. If the module is new, add it to `_CHILDREN`.
8. Document the endpoint here in `07-api-mobile.md` — including
   `[VERIFY]` markers if the exact field names are unknown, so the
   next session knows to check.
9. Add a test in `tests/integration/test_mobile_api.py` (creating
   the file if it doesn't exist — that's the ADR-019 promotion).

---

*Part 6b of 10. See `08-services.md` next.*