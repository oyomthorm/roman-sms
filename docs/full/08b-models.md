# Part 7b — Data model reference

The schema, table by table. Twelve modules, twenty-five `db.Model`
classes, seven migrations in the current chain. Every column group,
every foreign key, every index. This is the reference you consult
before writing a query or a migration.

**Note on `[VERIFY:]` markers.** `STRUCTURE.md` names the classes and
tables but does not enumerate every column with its type. Where a
column exists but its type is uncertain, a marker names the check.
Everything else — module groupings, table names, known field
additions, foreign key targets — is from `STRUCTURE.md` and the
migration chain in `02-architecture.md`.

## 7b.1 The import-order gotcha

`app/models/__init__.py` imports **`District` first** and calls
`configure_mappers()`. This fails loudly on any future import-order
mistake. If you add a model that has a foreign key to another model,
the target must be imported before the dependent — but District is
the special case that must come before everything because
`Contact.district_id` is an FK to `district.id` and `Contact` is
imported early.

The `configure_mappers()` call triggers SQLAlchemy to resolve all
relationships at import time. A relationship that points at an
unimported model fails here, not at first query — so the failure is
in your face during `flask run`, not three requests in.

## 7b.2 Module map

| Module | Classes | Tables |
|---|---|---|
| `organization.py` | `Organization`, `User`, `Plan`, `Subscription` | `organization`, `user`, `plan`, `subscription` |
| `messaging.py` | `Group`, `Contact`, `MessageTemplate`, `Campaign`, `MessageLog` | `contact_group`, `contact`, `message_template`, `campaign`, `message_log` |
| `ops.py` | `SendQueue`, `OptOut`, `AuditLog`, `NotificationDismissal` | `send_queue`, `opt_out`, `audit_log`, `notification_dismissal` |
| `wallet.py` | `WalletTransaction`, `Invoice` | `wallet_transaction`, `invoice` |
| `pool.py` | `PoolPermission`, `PoolContact` | `pool_permission`, `pool_contact` |
| `scheduling.py` | `CampaignSchedule` | `campaign_schedule` |
| `chat.py` | `ChatChannel`, `ChatMessage`, `ChatReadState` | `chat_channel`, `chat_message`, `chat_read_state` |
| `geo.py` | `District` | `district` |
| `imports.py` | `ContactImport`, `ContactImportIssue` | `contact_import`, `contact_import_issue` |
| `signup.py` | `SignupRequest` | `signup_request` |
| `api.py` | `ApiToken`, `ApiIdempotency` | `api_tokens`, `api_idempotency` |

**`User` inherits `UserMixin` first, `db.Model` second**
(`class User(UserMixin, db.Model)`). `current_user` is a `User` with
Flask-Login methods (`is_authenticated`, `get_id`). Any serializer or
service touching `current_user` should treat it as a `User`, not a
raw row.

## 7b.3 `organization.py`

### `Organization` — table `organization`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `name` | String | Display name |
| `slug` | String unique | URL slug, indexed — `[VERIFY: length, exact index name]` |
| `contact_email` | String | |
| `phone` | String | |
| `address` | String | |
| `is_master` | Boolean | True for org 1 only |
| `is_system` | Boolean | True for org 2 only |
| `active` | Boolean | Guarded by `_refuse_if_protected` for orgs 1, 2 |
| `vertical` | String(40) nullable, indexed | `'school'`, `'business'`, or NULL (feature #45) |
| `created_at` | DateTime | |

**The three orgs:**

- Org 1 (`roman-sms`): master. `is_master=True`.
- Org 2 (`roman-platform`): system sender. `is_system=True`.
- Org 3+: associates. Both flags False.

The system org is **invisible to associates** — every query listing
associates filters `is_system=False`. Master sees both master and
system orgs; associates see neither, except as an FK reference.

### `User` — table `user`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `email` | String unique | Login identifier |
| `password_hash` | String | Werkzeug hash |
| `name` | String | |
| `role` | String | `'master_admin'`, `'associate_admin'`, `'associate_user'` |
| `org_id` | FK → `organization.id` | Tenant scope |
| `department` | String(40) nullable, indexed | `'bursar'`, `'dos'`, `'dean'`, `'ht'`, or NULL (A1) |
| `is_active_flag` | Boolean | Mirrors `status`, kept in sync |
| `status` | String, default `'active'` | `'active'` / `'suspended'` / `'terminated'` (#46) |
| `status_changed_at` | DateTime nullable | |
| `created_at` | DateTime | |
| `last_login_at` | DateTime nullable | |

**`is_active_flag` vs `status`.** `is_active_flag` is what Flask-Login
checks. `status` is the source of truth; they are kept in sync by
`orgs.suspend_user`, `terminate_user`, `reactivate_user`:

- suspend → `status='suspended'`, `is_active_flag=True`
- terminate → `status='terminated'`, `is_active_flag=False`
- reactivate → `status='active'`, `is_active_flag=True`

Redundancy is deliberate — rewriting Flask-Login's dependency is a
larger blast radius than keeping a second field in sync.

### `Plan` — table `plan`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `name` | String | |
| `description` | String | |
| `price_ugx` | Numeric | Decimal — serialized as string in API |
| `credits` | Integer | Messages granted per plan period |
| `validity_days` | Integer | |
| `max_per_minute` | Integer | Rate limit |
| `max_per_day` | Integer | Rate limit |
| `created_at` | DateTime | |

Plans are snapshotted into Invoice and Subscription on issue — the
snapshot is what matters for the customer, not the live plan.

### `Subscription` — table `subscription`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `org_id` | FK → `organization.id` | |
| `plan_snapshot` | JSON | Frozen copy of Plan at subscription time |
| `started_at` | DateTime | |
| `expires_at` | DateTime | |
| `status` | String | `'active'` / `'expired'` |

**The snapshot is the source of truth.** `entitlements.check_can_send`
reads the snapshot for rate limits and validity, not the live Plan.

## 7b.4 `messaging.py`

### `Group` — table `contact_group`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `org_id` | FK → `organization.id`, indexed | |
| `name` | String | |
| `description` | String | |
| `department` | String(40) nullable, indexed | A1 |

`Group` has `contacts` relationship (one-to-many via `Contact.group_id`).

### `Contact` — table `contact`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `org_id` | FK → `organization.id`, indexed | |
| `name` | String nullable | |
| `phone` | String | Normalized via `phones.normalize_ug` |
| `group_id` | FK → `contact_group.id` **NOT NULL** | Migration 6c7a338d1274 |
| `district_id` | FK → `district.id` nullable | |
| `notes` | String nullable | |
| `opted_out` | Boolean default False | |
| `created_at` | DateTime | |

**`group_id` is NOT NULL** as of migration `6c7a338d1274`. A contact
must belong to a group. Ungrouped contacts from older imports were
assigned to a default group by that migration.

**Phone uniqueness.** Unique per org — `[VERIFY: is it a compound
UNIQUE (org_id, phone) or a service-level check?]`. From the contacts
service, duplicates within an org are rejected — whether by DB
constraint or service guard affects how race conditions are handled.

### `MessageTemplate` — table `message_template`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `org_id` | FK → `organization.id`, indexed | |
| `name` | String | |
| `body` | Text | Contains `{{column}}` or `{{name}}` placeholders |
| `department` | String(40) nullable, indexed | A1 |

### `Campaign` — table `campaign`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `org_id` | FK → `organization.id`, indexed | |
| `name` | String | |
| `body` | Text | Final rendered body or template? — `[VERIFY: for personalized campaigns, is `body` the template or the last-rendered version?]` |
| `status` | String | `'pending'` / `'sending'` / `'complete'` / `'cancelled'` |
| `total_segments` | Integer | Total cost |
| `created_by` | FK → `user.id` | |
| `created_at` | DateTime | |
| `completed_at` | DateTime nullable | |
| `department` | String(40) nullable, indexed | A1 |

`Campaign` has `logs` relationship (one-to-many via `MessageLog.campaign_id`).

### `MessageLog` — table `message_log`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `campaign_id` | FK → `campaign.id` nullable, indexed | NULL for schedule-sourced messages? — `[VERIFY: does a schedule create Campaign rows, or MessageLog directly?]` |
| `org_id` | FK → `organization.id`, indexed | Denormalized for queries |
| `phone` | String | Recipient |
| `body` | Text | Final rendered text (post-personalization) |
| `status` | String | `'pending'` / `'sent'` / `'failed'` / `'delivered'` / `'delivery_failed'` |
| `provider_ref` | String nullable | Pahappa's message ID |
| `sent_at` | DateTime nullable | |
| `created_at` | DateTime | |

**`body` is the final rendered text**, not a template reference. For
personalized campaigns, each `MessageLog.body` differs — this is why
the log grows quickly for personalized sends.

**`status` transitions** — the state machine enforced by `dispatch`:

    pending -> sent -> delivered
                    -> delivery_failed
    pending -> failed (on provider send failure)

## 7b.5 `ops.py`

### `SendQueue` — table `send_queue`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `campaign_id` | FK → `campaign.id`, indexed | |
| `status` | String | `'pending'` / `'processing'` / `'done'` / `'failed'` |
| `run_after` | DateTime | Scheduled start |
| `attempts` | Integer default 0 | |
| `last_error` | String nullable | |
| `created_at` | DateTime | |

Worker claims with `SELECT ... FOR UPDATE SKIP LOCKED` — see
`dispatch.claim_jobs`.

### `OptOut` — table `opt_out`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `phone` | String unique, indexed | Normalized phone |
| `reason` | String nullable | |
| `created_at` | DateTime | |

**Not scoped to org.** An opt-out is global — a phone that opted out
against one org is opted out against every org. This is deliberate
(Ugandan telecom policy: opt-out is absolute). `propagate_opt_out`
touches this table from every opt-out path.

### `AuditLog` — table `audit_log`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `actor_id` | FK → `user.id` nullable, indexed | NULL for system actions |
| `action` | String, indexed | e.g. `'user.create'`, `'wallet.grant'` |
| `target_type` | String nullable | |
| `target_id` | Integer nullable | |
| `details` | JSON nullable | |
| `created_at` | DateTime, indexed | |

**Append-only.** No row updated or deleted. See `audit.log` and the
commits-own-transaction behavior in `08-services.md` §7a.21.

### `NotificationDismissal` — table `notification_dismissal`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | FK → `user.id`, indexed | |
| `key` | String | Notification identifier |
| `dismissed_at` | DateTime | |

Unique (user_id, key) — `[VERIFY: is it a compound unique or a
service-level guard?]`. A user dismisses a specific notification key;
the same key does not reappear unless the notification is regenerated
with a fresh key.

## 7b.6 `wallet.py`

### `WalletTransaction` — table `wallet_transaction`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `org_id` | FK → `organization.id`, indexed | |
| `delta` | Integer | Positive for credit, negative for debit |
| `balance_after` | Integer | Balance snapshot after this transaction |
| `reason` | String, indexed | From `EXTERNAL_CREDIT_REASONS` or internal debit reasons |
| `reference` | String nullable | e.g. `campaign:123`, `schedule:45` |
| `source_org_id` | FK → `organization.id` nullable | Set for internal transfers |
| `notes` | String nullable | |
| `actor_id` | FK → `user.id` nullable | Who triggered |
| `created_at` | DateTime, indexed | |

**Append-only.** No update, no delete. `get_balance` is
`SUM(delta)`; `balance_after` is a denormalized convenience.

**Invariant:** `SUM(delta) == max(created_at).balance_after`.
`scripts/reconcile.py` verifies this.

### `Invoice` — table `invoice`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `org_id` | FK → `organization.id`, indexed | |
| `plan_snapshot` | JSON | Frozen Plan at issue time |
| `amount_ugx` | Numeric | Decimal — serialized as string |
| `credits` | Integer | Snapshot |
| `status` | String | `'pending'` / `'paid'` / `'cancelled'` |
| `issued_by` | FK → `user.id` | |
| `issued_at` | DateTime | |
| `paid_at` | DateTime nullable | |

**The snapshot is what the PDF shows.** No live lookup in
`invoice_pdf.render`.

## 7b.7 `pool.py`

### `PoolPermission` — table `pool_permission`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `org_id` | FK → `organization.id` unique | One permission per org |
| `agreement_text` | Text | Verbatim text accepted |
| `granted_at` | DateTime | |
| `revoked_at` | DateTime nullable | NULL if active |

**The agreement text is stored verbatim**, not a reference to the
current text. If the wording changes tomorrow, the old permissions
still say what was accepted.

### `PoolContact` — table `pool_contact`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `source_org_id` | FK → `organization.id`, indexed | |
| `phone` | String, indexed | Normalized |
| `name` | String nullable | Snapshot |
| `group_name` | String nullable | Snapshot |
| `district_id` | FK → `district.id` nullable | Snapshot |
| `opted_out` | Boolean | Propagated |
| `snapshot_at` | DateTime | |

**Snapshot semantics.** Renaming a source group does not change
`group_name` on existing pool contacts. Adding contacts to a group
does not add pool contacts. Only re-granting (revoke then grant)
refreshes the snapshot.

## 7b.8 `scheduling.py`

### `CampaignSchedule` — table `campaign_schedule`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `org_id` | FK → `organization.id`, indexed | |
| `name` | String | |
| `body` | Text | Template or final body — `[VERIFY: for personalized schedules, is body stored per-fire or once?]` |
| `group_id` | FK → `contact_group.id` nullable | Orphan guard absent (backlog #38) |
| `district_id` | FK → `district.id` nullable | |
| `days_of_week` | String | JSON array or comma-separated — `[VERIFY]` |
| `times` | Text | JSON array of `"HH:MM"` strings |
| `start_date` | Date | |
| `end_date` | Date | |
| `status` | String | `'active'` / `'paused'` / `'completed'` / `'cancelled'` |
| `last_run_at` | DateTime nullable | |
| `next_run_at` | DateTime nullable, indexed | |
| `runs_completed` | Integer default 0 | |
| `credits_reserved` | Integer nullable | NULL = legacy pre-#44; else current reservation |
| `created_by` | FK → `user.id` | |
| `department` | String(40) nullable, indexed | A1 |
| `created_at` | DateTime | |

**`credits_reserved` drives the whole #44 flow.** If NULL, the
schedule debits at fire (legacy). If set, the reservation was debited
at create; fire decrements the column and refunds at completion/
cancellation.

**`days_of_week` storage** — `[VERIFY: exact format. The `times` field
is JSON; `days_of_week` may be JSON or a comma-separated string. Check
`schedules.create_schedule` for how the form value is stored.]`

## 7b.9 `chat.py`

### `ChatChannel` — table `chat_channel`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `kind` | String | `'dm'` / `'broadcast'` |
| `participant_a_id` | FK → `user.id` nullable | For DMs, one participant |
| `participant_b_id` | FK → `user.id` nullable | For DMs, the other |
| `created_at` | DateTime | |

**Broadcast channels have NULL participants** — every user in the
system sees the broadcast channel. DMs have two participants.

**DM channel uniqueness** — `[VERIFY: is a DM channel created once
per pair and reused, or per conversation session?]`.

### `ChatMessage` — table `chat_message`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `channel_id` | FK → `chat_channel.id`, indexed | |
| `sender_id` | FK → `user.id`, indexed | |
| `body` | Text | |
| `sent_at` | DateTime, indexed | |

### `ChatReadState` — table `chat_read_state`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `channel_id` | FK → `chat_channel.id`, indexed | |
| `user_id` | FK → `user.id`, indexed | |
| `last_read_message_id` | FK → `chat_message.id` nullable | |
| `updated_at` | DateTime | |

Unique (channel_id, user_id) — one read-state row per user per channel.

## 7b.10 `geo.py`

### `District` — table `district`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `name` | String unique, indexed | |
| `region` | String nullable | |

Seeded once via `flask seed-districts`. Not edited after seeding
(rural districts don't rename).

## 7b.11 `imports.py`

### `ContactImport` — table `contact_import`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `org_id` | FK → `organization.id`, indexed | |
| `filename` | String | |
| `status` | String | `'pending'` / `'complete'` / `'failed'` |
| `total_rows` | Integer | |
| `imported` | Integer | |
| `skipped_invalid` | Integer | |
| `skipped_optout` | Integer | |
| `skipped_dup_file` | Integer | |
| `skipped_dup_db` | Integer | |
| `skipped_no_group` | Integer | Migration `6c7a338d1274` added this |
| `created_by` | FK → `user.id` | |
| `created_at` | DateTime | |

### `ContactImportIssue` — table `contact_import_issue`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `import_id` | FK → `contact_import.id`, indexed | |
| `row_number` | Integer | |
| `reason` | String | `'invalid_phone'`, `'opted_out'`, `'dup_file'`, `'dup_db'`, `'no_group'` |
| `raw_row` | JSON | Original row data for the error CSV |

**The persistent report.** Every skipped row is a `ContactImportIssue`
row. `/contacts/imports/<id>` shows counts by reason; `/contacts/imports/
<id>/errors.csv` downloads them.

## 7b.12 `signup.py`

### `SignupRequest` — table `signup_request`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `org_name` | String | Proposed |
| `slug` | String | Proposed |
| `contact_name` | String | Applicant |
| `email` | String | |
| `phone` | String | |
| `address` | String nullable | |
| `vertical` | String nullable | `'school'` / `'business'` / NULL |
| `status` | String | `'pending'` / `'approved'` / `'rejected'` |
| `reviewed_by` | FK → `user.id` nullable | |
| `reviewed_at` | DateTime nullable | |
| `rejection_reason` | String nullable | |
| `created_at` | DateTime | |

**The public form creates only this row.** No Organization, no User.
Org creation happens in `signups.approve` — see `08-services.md` §7a.16.

## 7b.13 `api.py`

### `ApiToken` — table `api_tokens`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | FK → `user.id`, indexed | |
| `token_hash` | String unique, indexed | SHA-256 of `rsms_<random>` |
| `created_at` | DateTime | |
| `expires_at` | DateTime | |
| `last_used_at` | DateTime nullable | |

**The hash, not the token.** `install_api_auth` hashes the incoming
Bearer value and looks up by `token_hash`. The plaintext is shown
once at login and never stored.

### `ApiIdempotency` — table `api_idempotency`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `key` | String, indexed | Client-supplied `Idempotency-Key` |
| `user_id` | FK → `user.id`, indexed | |
| `response_status` | Integer | |
| `response_body` | Text | Stored response to replay |
| `created_at` | DateTime, indexed | |

**Unique (key, user_id)** — same key by different users is allowed
(they're on different campaigns).

**TTL.** No automatic expiry today — old idempotency records
accumulate. `[VERIFY: is there a cleanup job? If not, this table
grows without bound.]`

## 7b.14 Migration chain

Seven revisions, linear:

    5e5fea16ea4e (base)
      +-- 00404835aeb7
          +-- 6c7a338d1274  (Contact.group_id NOT NULL, ContactImport.skipped_no_group)
              +-- e5997cc4f270  (A1: 5 department columns)
                  +-- c41928d919da  (#44: campaign_schedule.credits_reserved)
                      +-- e37cc1348332  (#46: user.status, user.status_changed_at)
                          +-- 87cd66d8578c  (#45: organization.vertical)

**Head: `87cd66d8578c`.** Verify with `flask db current` before any
deploy that touches models. A deploy that runs the app against a stale
schema will fail at the first query that touches a missing column.

**Migration rules:**

- Never edit a live revision. Migrations are immutable once pushed.
  If a migration has a bug, add a new one to fix it.
- Migrations are forward-only in practice — down() exists but is not
  exercised in production.
- Verify against the actual database with `flask db current` after
  apply, not just "migrate didn't error."

## 7b.15 The A1–#16 field additions (summary)

Fields added in the arc, cross-referenced to their features:

| Field | Model | Migration | Feature |
|---|---|---|---|
| `User.department` | user | e5997cc4f270 | A1 |
| `Contact_group.department` | contact_group | e5997cc4f270 | A1 |
| `Message_template.department` | message_template | e5997cc4f270 | A1 |
| `Campaign.department` | campaign | e5997cc4f270 | A1 |
| `Campaign_schedule.department` | campaign_schedule | e5997cc4f270 | A1 |
| `Campaign_schedule.credits_reserved` | campaign_schedule | c41928d919da | #44 |
| `User.status` | user | e37cc1348332 | #46 |
| `User.status_changed_at` | user | e37cc1348332 | #46 |
| `Organization.vertical` | organization | 87cd66d8578c | #45 |
| `ContactImport.skipped_no_group` | contact_import | 6c7a338d1274 | post-A1 |

All are nullable or defaulted, so no backfill was required for existing
rows. The migration `e5997cc4f270` added five department columns
across five tables; each is `String(40), nullable, indexed`.

## 7b.16 Adding a new model (checklist)

1. New file or extend an existing file in `app/models/`.
2. Class inherits `db.Model`. If it needs Flask-Login, inherit
   `UserMixin` **first**.
3. Define `__tablename__` explicitly — do not rely on the default
   (PluralRule makes `User` become `users`, but the codebase uses
   `user`, `contact`, etc.).
4. If it needs a foreign key to another model, that model must be
   imported in `app/models/__init__.py` **before** this one. District
   is imported first, always.
5. Add any indexes explicitly — SQLAlchemy does not auto-index FKs.
6. Import the model in `app/models/__init__.py` at the right position.
7. Generate the migration: `flask db migrate -m "..."`. Review the
   generated migration — it may not detect data migrations.
8. Run `flask db upgrade` on a dev DB. Verify with `flask db current`.
9. Add the model to `STRUCTURE.md` and to this file (Part 7b).
10. If the model participates in a state machine (like `MessageLog`
    status), document the transitions here.

## 7b.17 Conventions

- **Integer primary keys**, autoincrement. No UUID PKs.
- **`created_at` DateTime** on every table that records events.
  `updated_at` only where mutation matters (`User.status_changed_at`).
- **FKs are `_id` suffixed** and refer to `Model.id`. The FK column
  name matches the relationship name.
- **Timestamps are naive UTC.** `iso()` in serializers emits them
  without a `Z` suffix. Clients must interpret them as UTC. See Part
  6b §6b.3.
- **Boolean flags are `is_*` or plain names** (`is_master`,
  `opted_out`, `active`). Not `flags.master`.
- **JSON columns are `db.JSON`** or `Text` with JSON serialization
  (check the model; both are in use).
- **`__repr__`** — not defined on most models. If you add one, keep it
  to `id` and one identifier field; do not trigger lazy loads.

---

*Part 7b of 10. See `09-operations.md` next.*