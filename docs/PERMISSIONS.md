# Permissions

Three roles. No permission tables.

## Matrix

| Action | master_admin | associate_admin | associate_user |
|---|:---:|:---:|:---:|
| **Master** | | | |
| Create/suspend associate org | ✅ | ❌ | ❌ |
| View/approve signups | ✅ | ❌ | ❌ |
| Grant credits | ✅ | ❌ | ❌ |
| Create/edit plans | ✅ | ❌ | ❌ |
| Issue invoice | ✅ | ❌ | ❌ |
| Mark invoice paid | ✅ | ❌ | ❌ |
| View all orgs and ledgers | ✅ | ❌ | ❌ |
| View master pool | ✅ | ❌ | ❌ |
| Send pool campaign | ✅ | ❌ | ❌ |
| View platform sender | ✅ | ❌ | ❌ |
| View audit log | ✅ | ❌ | ❌ |
| **Associate billing** | | | |
| View own wallet | ✅ | ✅ | ✅ |
| Create invoice (buy plan) | ❌ | ✅ | ❌ |
| **Associate settings** | | | |
| Edit org settings | ✅ | ✅ | ❌ |
| Grant/revoke pool permission | ❌ | ✅ | ❌ |
| Reset user passwords (within org) | ✅ | ✅ | ❌ |
| Invite / deactivate users | ✅ | ❌ | ❌ |
| Change user roles (within org) | ✅ | ❌ | ❌ |
| **Associate messaging** | | | |
| View contacts | ✅ | ✅ | ✅ |
| Add / import contacts | ✅ | ✅ | ✅ |
| View import reports | ✅ | ✅ | ✅ |
| Mark contact opted-out | ✅ | ✅ | ✅ |
| Create / send campaigns | ✅ | ✅ | ✅ |
| Cancel own campaigns | ✅ | ✅ | ✅ |
| View reports | ✅ | ✅ | ✅ |
| **Communication** | | | |
| Use chat (DM + broadcast) | ✅ | ✅ | ✅ |
| View own profile / change password | ✅ | ✅ | ✅ |
| **Public (unauthenticated)** | | | |
| Submit signup request | ✅ | ✅ | ✅ |
| Opt out (via link or landing) | ✅ | ✅ | ✅ |

> **Not yet available.** Inviting / deactivating users and changing
> user roles within an associate org are parked (see `SCOPE.md` and
> `BACKLOG.md`: "Per-associate sub-users UI — est. 3d"). Until that
> ships, `associate_admin` can reset passwords for existing users but
> cannot create or remove them. Master retains full user management
> for any org.

## Enforcement layers

1. **Route decorator.** `@master_required`, `@org_admin_required`, or
   none. Blocks the handler entirely.
2. **Query scoping.** Every tenant read goes through `org_scoped(Model)`.
   Filters rows by `current_user.org_id` unless the user is master.
3. **Service guard.** `check_can_send`, `check_contact_limit`,
   `_refuse_if_protected` in `orgs`. Blocks the action even if the route
   and query got through.

Each layer catches what the previous one might miss.

## Rules

- `org_id` never comes from `request.form`, `request.args`, or the URL.
  It always comes from `current_user.org_id`.
- Every route with `org_id` in the path is `@master_required`.
- Every insert sets `org_id = current_user.org_id`.
- A user cannot be created with the `master_admin` role except by
  another master.
- `_refuse_if_protected` in `orgs.py` blocks all writes to the master
  and system orgs.
- The system org is invisible to associates. Every query that lists
  associates filters `is_system=False`.
- Public signup routes are CSRF-protected and rate limited. They never
  create an Organization directly — only a `SignupRequest`.

## Adding a new role

When a paying associate asks and three have asked independently:

1. Add a row to the matrix above.
2. Add the role to the `role_required(...)` decorator where it applies.
3. Add a check to `check_contact_limit` or the relevant service guard.
4. Add a test in `tests/integration/test_permissions.py` for each
   boundary the new role crosses.

Do not add a permission table until at least five roles exist. Three
roles, three checks, no system.