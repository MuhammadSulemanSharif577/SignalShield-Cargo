# SignalShield Cargo API

FastAPI with the existing presentation → application/use cases → domain interfaces →
infrastructure/repositories architecture. SQLAlchemy persists users, roles, revocable
sessions, fleet records, and dashboard sources.
The frontend API is served under `/api/v1` (OpenAPI: `/docs`).

## Run

From `backend/` with Python 3.11+:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .envExample .env
# Set DATABASE_URL, a strong JWT_SECRET_KEY, and CORS_ORIGINS in .env.
alembic upgrade head
python -m app.bootstrap --email admin@example.com --name "Administrator"
uvicorn app.main:app --reload
```

The bootstrap command prompts for a password. It initializes an administrator role
with backend-owned locked `users:manage`/`roles:manage` permissions and will not run
again after users have roles. Existing users from the original schema are preserved;
bootstrap can promote an existing email. There is no public registration endpoint.
Alembic upgrades both a fresh database and the original users-only database. Importing
the API does not create or change tables. Use `alembic check` to check schema drift.

## Authentication and user provisioning

Login uses email and password. Password recovery, email MFA, invitation emails,
and SMTP delivery are not supported; no email server or worker is needed.

Administrators create users with `POST /api/v1/users`:

```json
{
  "name": "New Operator",
  "email": "operator@example.com",
  "roleIds": ["an-existing-role-id"],
  "password": "SecurePassword123"
}
```

The initial password must contain at least 10 characters, an uppercase letter, a
lowercase letter, and a number. Passwords are hashed and never returned by user
endpoints. Share initial credentials through a secure channel. New users remain
pending until an administrator activates them with
`PATCH /api/v1/users/{id}` and `{"status": "active"}`.

Existing installations must run `alembic upgrade head`. The removal migration
deletes queued emails, password-reset tokens, and email MFA challenges/enrollment.
Existing users and password hashes are preserved; previously MFA-enabled users
must sign in again using their password. Downgrading recreates empty tables but
cannot recover deleted email data or MFA enrollment.

Sessions are opaque random bearer tokens, stored only as keyed hashes in the database.
`JWT_SECRET_KEY` is retained as the secret setting used to key those hashes; changing
it invalidates outstanding tokens. Refresh rotates the bearer token and
loads current role names/permissions. Logout revokes the presented session.

## Authorization and fleet rules

- User reads accept `users:view` or `users:manage`; role reads also support user
  management screens. Role mutations require `roles:manage`.
- Fleet list/detail endpoints require the matching `*:view`; normal changes require
  `*:manage`. Assignable drivers require `drivers:view`.
- Driver phone numbers require `drivers:manage`; driver emails require
  `drivers:manage` or `drivers:credentials`. Linked user metadata and credential
  changes require `drivers:credentials`; only create/reset returns a temporary password.
  Credentials store Argon2 hashes in `users`; reset, revoke, and driver deactivation
  invalidate sessions directly.
- Driver phone numbers are normalized for uniqueness. Driver emails are required,
  trimmed, lowercased, and unique; registrations are uppercase. Receivers and vehicle
  assignments are also unique at the database level.
- Only active drivers/vehicles can be newly assigned. Unassign a driver's vehicle
  before deactivation. Current active/delayed journeys prevent reassignment,
  deactivation, or receiver replacement. One live journey per vehicle/driver is
  enforced with partial unique indexes.
- Journey histories require journey permissions; alert/incident timelines require
  their corresponding permissions. Locations require `tracking:view`.

### Shared user identities and driver profiles

Register or edit a driver with `{name, phone, email}`. An empty, missing, null, or
invalid email returns `422 validation`; an email conflict returns `409 conflict`.
Registration creates only the driver record.

`users` is the single authentication table for staff and drivers. `drivers.user_id`
is an optional, unique foreign key to `users.id`; driver records without login
access have no linked user. `mobile_accounts` is no longer used.

`POST /api/v1/drivers/{id}/credentials` takes **no body** and creates an active user
using the saved driver name/email, linking it to the driver and assigning the fixed
built-in Driver role (`builtin-driver`, permission `driver:access`). That role grants
no staff or fleet-wide access. It cannot be edited or assigned through staff-user
creation. Existing user emails produce a conflict; accounts are never silently
merged or overwritten. The driver must be active and not already linked.

Creation and `POST /api/v1/drivers/{id}/credentials/reset-password` return
`{driver, email, temporaryPassword}`; driver responses contain
`userAccount: {id, email, status, mustChangePassword, createdAt, lastLogin}`.
Reset keeps the same user identity, enables the account, revokes all its sessions,
and requires a password change. `DELETE /api/v1/drivers/{id}/credentials` returns 204,
disables the linked user, and revokes sessions; neither record is deleted.
Use reset to restore access. Deactivating a driver also disables its user;
reactivating the operational profile does not automatically restore login access.

Both staff and drivers use `POST /api/v1/auth/login` with `{email, password}`.
The session's `user` includes `driverId` (null for staff) and `mustChangePassword`.
Temporary-password sessions have no effective permissions and cannot use protected
operations until `POST /api/v1/auth/change-password` with
`{currentPassword, newPassword}` succeeds. It returns a rotated session, revokes all
older sessions, and clears the flag. `GET /api/v1/auth/me` returns the current user's
own identity and password-change flag. Driver operational/mobile endpoints remain
future work and must enforce ownership, not grant fleet-wide permissions.

User list responses include `driverId` and `mustChangePassword`, so linked accounts
appear in the same directory as staff. Change linked names/emails from the driver
profile; the user identity is synchronized atomically and email changes revoke
sessions without changing the password. Linked roles are fixed; Users can change
their active/inactive login status only, and cannot activate a deactivated driver.

**Existing databases:** back up the database and run `alembic upgrade head`.
Migration `0003_driver_email_login` validates/normalizes driver emails and removes
legacy usernames. Migration `0004_unified_driver_users` moves existing password hashes,
creation/login timestamps, temporary-password flags, and effective account status
into linked users before removing `mobile_accounts`. Drivers without credentials
remain unlinked. User email collisions and a conflicting Driver role ID/name stop
the migration before its changes; resolve them explicitly and rerun.
Downgrading recreates legacy credentials but keeps unified user identities to avoid
data loss; upgrading again may require resolving those duplicate identities.
Legacy credential versions are replaced by revocable shared sessions. Mobile client
integration is a separate follow-up; `mobile/` has not been changed.

## Dashboard data

`GET /api/v1/dashboard/summary` requires `dashboard:view`. It aggregates persisted
vehicles, drivers, journeys, shipments, security records, and GNSS recordings, with
per-section timestamps and an exhaustive severity/status matrix. Each section is
redacted server-side based on the frontend permission vocabulary. Journey integrity
is `not_assessed` without analysis/alert access; location timestamps require tracking
access. Activity is filtered per event kind. User/role changes write activity records
in the same transaction as the change. No sample records are seeded.

Operational integrations populate the corresponding database models in
`app/infrastructure/database/models/`: vehicle `device`/`last_location`, `JourneyModel`,
`ShipmentModel`, `RecordingModel`, `DriverRecordModel` (`kind=alert|incident`),
`DeviceIssueModel`, and `ActivityModel`. Device JSON follows `DeviceInfo` (snake_case
or camelCase keys); positions use `{lat, lng, at}`. Store UTC-aware timestamps.
Receiver reporting requires a real `ok` report from the past five minutes. Daily
recording counts use UTC. Incidents awaiting review are represented as investigating
in driver timelines, whose status vocabulary differs from dashboard incidents.

Empty aggregates are zero, lists are `[]`, and never-received section timestamps
are null. Fleet timestamps reflect fleet writes; GNSS/device timestamps reflect real
telemetry rather than vehicle registration time.

## Verify

```sh
pip install -r requirements-dev.txt
pytest -q
# Optional: include PostgreSQL locking/concurrency checks with a dedicated, empty test DB:
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost/signalshield_test pytest -q
```

Tests use isolated SQLite databases by default, exercise the HTTP contract and
authorization, and check migrations against both fresh and legacy schemas. A dedicated
`TEST_DATABASE_URL` enables PostgreSQL concurrency tests; its application tables are
created and dropped between tests. PostgreSQL is the deployment database; locking
and uniqueness constraints live in repositories/models.
