"""Move driver credentials into users and link optional driver profiles."""

from alembic import op
import sqlalchemy as sa

revision = "0004_unified_driver_users"
down_revision = "0003_driver_email_login"
branch_labels = None
depends_on = None

DRIVER_ROLE_ID = "builtin-driver"


def upgrade():
    connection = op.get_bind()
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, autoload_with=connection)
    drivers = sa.Table("drivers", metadata, autoload_with=connection)
    accounts = sa.Table("mobile_accounts", metadata, autoload_with=connection)
    roles = sa.Table("roles", metadata, autoload_with=connection)
    existing_emails = {}
    # Validate before any DDL/data changes. Never merge identities by email.
    for row in connection.execute(sa.select(users.c.id, users.c.email)):
        email = row.email.strip().lower()
        if email in existing_emails:
            raise RuntimeError(f"Users {existing_emails[email]} and {row.id} have conflicting emails; resolve before migration.")
        existing_emails[email] = row.id
    legacy = connection.execute(sa.select(
        drivers.c.id.label("driver_id"), drivers.c.name, drivers.c.email,
        drivers.c.status.label("driver_status"), accounts.c.password_hash,
        accounts.c.active, accounts.c.must_change_password,
        accounts.c.created_at, accounts.c.last_login_at,
    ).join(accounts, drivers.c.id == accounts.c.driver_id)).mappings().all()
    for account in legacy:
        if account["email"] in existing_emails:
            raise RuntimeError(
                f"Driver {account['driver_id']} email conflicts with user {existing_emails[account['email']]}; "
                "resolve the two identities before migration. Neither account was changed."
            )
    if connection.execute(sa.select(roles.c.id).where(
        sa.or_(roles.c.id == DRIVER_ROLE_ID, roles.c.name_key == "driver")
    )).first():
        raise RuntimeError("The built-in Driver role ID/name is already in use; resolve before migration.")

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.false()))
    with op.batch_alter_table("drivers") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer, nullable=True))
        batch.create_foreign_key("fk_drivers_user_id", "users", ["user_id"], ["id"], ondelete="RESTRICT")
        batch.create_unique_constraint("uq_drivers_user_id", ["user_id"])
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, autoload_with=connection)
    drivers = sa.Table("drivers", metadata, autoload_with=connection)
    user_roles = sa.Table("user_roles", metadata, autoload_with=connection)
    connection.execute(roles.insert().values(
        id=DRIVER_ROLE_ID, name="Driver", name_key="driver",
        description="Driver account; no staff or fleet-wide access.",
        permissions=["driver:access"], built_in=True, locked_permissions=["driver:access"],
    ))
    for email, user_id in existing_emails.items():
        connection.execute(users.update().where(users.c.id == user_id).values(email=email))
    for account in legacy:
        active = account["active"] and account["driver_status"] == "active"
        user_id = connection.execute(users.insert().values(
            full_name=account["name"], email=account["email"],
            hashed_password=account["password_hash"], is_active=active,
            status="active" if active else "inactive",
            must_change_password=account["must_change_password"],
            created_at=account["created_at"], last_login=account["last_login_at"],
        ).returning(users.c.id)).scalar_one()
        connection.execute(drivers.update().where(drivers.c.id == account["driver_id"]).values(user_id=user_id))
        connection.execute(user_roles.insert().values(user_id=user_id, role_id=DRIVER_ROLE_ID))
    op.drop_table("mobile_accounts")


def downgrade():
    op.create_table("mobile_accounts",
        sa.Column("driver_id", sa.String(64), sa.ForeignKey("drivers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("must_change_password", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("credential_version", sa.Integer, nullable=False),
    )
    connection = op.get_bind()
    # Preserve the current shared password; legacy credential versions restart.
    connection.execute(sa.text(
        "INSERT INTO mobile_accounts "
        "(driver_id, password_hash, active, must_change_password, created_at, last_login_at, credential_version) "
        "SELECT d.id, u.hashed_password, (u.status = 'active' AND d.status = 'active'), "
        "u.must_change_password, u.created_at, u.last_login, 1 "
        "FROM drivers d JOIN users u ON u.id = d.user_id"
    ))
    with op.batch_alter_table("drivers") as batch:
        batch.drop_constraint("uq_drivers_user_id", type_="unique")
        batch.drop_constraint("fk_drivers_user_id", type_="foreignkey")
        batch.drop_column("user_id")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("must_change_password")
    connection.execute(sa.text("DELETE FROM user_roles WHERE role_id = :id"), {"id": DRIVER_ROLE_ID})
    connection.execute(sa.text("DELETE FROM roles WHERE id = :id"), {"id": DRIVER_ROLE_ID})
    # Keep user identities: deleting them could destroy newer account data.
