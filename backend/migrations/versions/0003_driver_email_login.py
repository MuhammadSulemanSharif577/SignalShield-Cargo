"""Use the required driver email as the single mobile login identity."""

from uuid import uuid4

from alembic import op
from pydantic import EmailStr, TypeAdapter, ValidationError
import sqlalchemy as sa

revision = "0003_driver_email_login"
down_revision = "0002_remove_email_flows"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    drivers = sa.table("drivers", sa.column("id", sa.String), sa.column("email", sa.String))
    emails = {}
    validator = TypeAdapter(EmailStr)
    # Check every record before changing data or schema. Never invent driver emails.
    for driver_id, email in connection.execute(sa.select(drivers.c.id, drivers.c.email)):
        try:
            normalized = validator.validate_python(email).lower()
        except ValidationError:
            raise RuntimeError(f"Driver {driver_id} needs a valid email before migration.") from None
        if normalized in emails:
            raise RuntimeError(
                f"Drivers {emails[normalized]} and {driver_id} need distinct emails before migration."
            )
        emails[normalized] = driver_id

    for email, driver_id in emails.items():
        connection.execute(drivers.update().where(drivers.c.id == driver_id).values(email=email))
    with op.batch_alter_table("drivers") as batch:
        batch.alter_column("email", existing_type=sa.String(255), nullable=False)
        batch.create_check_constraint(
            "driver_email_normalized", "email = lower(trim(email)) AND length(email) > 0"
        )
    with op.batch_alter_table("mobile_accounts") as batch:
        batch.drop_column("username")
    # Existing mobile sessions must reauthenticate using the new login identity.
    op.execute(sa.text("UPDATE mobile_accounts SET credential_version = credential_version + 1"))


def downgrade():
    # Old usernames cannot be recovered. Assign unique, valid legacy usernames.
    with op.batch_alter_table("mobile_accounts") as batch:
        batch.add_column(sa.Column("username", sa.String(32), nullable=True))
    accounts = sa.table("mobile_accounts", sa.column("driver_id", sa.String), sa.column("username", sa.String))
    connection = op.get_bind()
    for driver_id in connection.execute(sa.select(accounts.c.driver_id)).scalars().all():
        connection.execute(accounts.update().where(accounts.c.driver_id == driver_id).values(username=uuid4().hex))
    with op.batch_alter_table("mobile_accounts") as batch:
        batch.alter_column("username", existing_type=sa.String(32), nullable=False)
        batch.create_unique_constraint("uq_mobile_accounts_username", ["username"])
    with op.batch_alter_table("drivers") as batch:
        batch.drop_constraint("driver_email_normalized", type_="check")
        batch.alter_column("email", existing_type=sa.String(255), nullable=True)
