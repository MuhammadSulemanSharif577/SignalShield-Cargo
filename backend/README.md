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
  `drivers:manage` or `drivers:credentials`. Mobile account metadata and credential
  changes require `drivers:credentials`; only create/reset returns a temporary password.
  Credentials store Argon2 hashes; resets increment `credential_version` to invalidate
  mobile sessions bound to an earlier credential version.
- Driver phone numbers are normalized for uniqueness. Driver emails are required,
  trimmed, lowercased, and unique; registrations are uppercase. Receivers and vehicle
  assignments are also unique at the database level.
- Only active drivers/vehicles can be newly assigned. Unassign a driver's vehicle
  before deactivation. Current active/delayed journeys prevent reassignment,
  deactivation, or receiver replacement. One live journey per vehicle/driver is
  enforced with partial unique indexes.
- Journey histories require journey permissions; alert/incident timelines require
  their corresponding permissions. Locations require `tracking:view`.

### Driver email-based mobile credentials

Register or edit a driver with `{name, phone, email}`. An empty, missing, null, or
invalid email returns `422 validation`; an email conflict returns `409 conflict`.
Registration creates only the driver record.

`POST /api/v1/drivers/{id}/credentials` takes **no body** and creates mobile access
using the saved driver email. It rejects inactive drivers and existing logins.
Creation and `POST /api/v1/drivers/{id}/credentials/reset-password` return
`{driver, email, temporaryPassword}`; driver responses use `mobileAccount.email`.
There is no username field. Reset requires an existing login and rotates its password
and credential version. `DELETE /api/v1/drivers/{id}/credentials` returns 204 and
keeps the driver email.

The driver record is the single source of the login email: mobile accounts store
the driver ID and password hash, not a duplicate email. Editing the driver email
therefore changes the login identity atomically without changing its password.
A conflict rolls back the entire edit. Mobile authentication integrations should
normalize the supplied email, look up `DriverModel.email`, join `MobileAccountModel`
by driver ID, check driver/account status and password, and enforce
`must_change_password` and `credential_version`. The admin `/auth/login` endpoint
remains for web users; this API does not yet expose a mobile session/password-change
endpoint.

**Existing databases:** back up the database and run `alembic upgrade head`.
Migration `0003_driver_email_login` validates and normalizes all driver emails
before making changes. It stops with the affected driver IDs if any email is missing,
invalid, or duplicated after normalization; correct those records and rerun.
It removes legacy mobile usernames, preserves password hashes and account metadata,
and increments credential versions to require mobile reauthentication.
Update mobile clients/integrations to use email before deploying this breaking change.
Downgrade cannot recover old usernames; it assigns random unique legacy usernames.

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
