"""Frontend contract schema; preserves the original users table and records."""

from alembic import op
import sqlalchemy as sa

revision = "0001_frontend_contract"
down_revision = None
branch_labels = None
depends_on = None


def identifier():
    return sa.Column("id", sa.String(64), primary_key=True)


def timestamp(name, nullable=False):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def reference(name, target, nullable=False, ondelete=None, **kwargs):
    return sa.Column(name, sa.String(64), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable, **kwargs)


def upgrade():
    if "users" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("users",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("full_name", sa.String(150), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("is_active", sa.Boolean, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("status", sa.String(16), nullable=False, server_default="active"))
        batch.add_column(sa.Column("mfa_enabled", sa.Boolean, nullable=False, server_default=sa.false()))
        batch.add_column(timestamp("last_login", nullable=True))
        batch.add_column(sa.Column("failed_logins", sa.Integer, nullable=False, server_default="0"))
        batch.add_column(timestamp("locked_until", nullable=True))
    op.execute(sa.text("UPDATE users SET status = 'inactive' WHERE is_active = false"))
    op.create_table("roles", identifier(),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("name_key", sa.String(150), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("permissions", sa.JSON, nullable=False),
        sa.Column("built_in", sa.Boolean, nullable=False),
        sa.Column("locked_permissions", sa.JSON, nullable=False),
    )
    op.create_table("user_roles",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.String(64), sa.ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True),
    )
    for table in ("access_sessions", "mfa_challenges", "password_reset_tokens"):
        columns = [identifier() if table == "mfa_challenges" else sa.Column("token_hash", sa.String(64), primary_key=True),
                   sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
                   timestamp("expires_at")]
        if table == "mfa_challenges":
            columns += [sa.Column("secret_hash", sa.String(64), nullable=False),
                        sa.Column("attempts", sa.Integer, nullable=False)]
        op.create_table(table, *columns)
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
    op.create_index("ix_access_sessions_expires_at", "access_sessions", ["expires_at"])
    op.create_table("email_outbox", identifier(),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False), timestamp("created_at"),
        timestamp("sent_at", nullable=True), sa.Column("attempts", sa.Integer, nullable=False),
        timestamp("next_attempt_at"), timestamp("expires_at"),
    )
    op.create_table("drivers", identifier(),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False, unique=True),
        sa.Column("email", sa.String(255), unique=True),
        sa.Column("status", sa.String(16), nullable=False), timestamp("updated_at"),
    )
    op.create_table("vehicles", identifier(),
        sa.Column("registration", sa.String(12), nullable=False, unique=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("model", sa.String(150), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        reference("driver_id", "drivers.id", nullable=True, unique=True),
        sa.Column("receiver_id", sa.String(150), unique=True),
        sa.Column("device", sa.JSON), sa.Column("last_location", sa.JSON), timestamp("updated_at"),
    )
    op.create_table("mobile_accounts",
        reference("driver_id", "drivers.id", primary_key=True, ondelete="CASCADE"),
        sa.Column("username", sa.String(32), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("must_change_password", sa.Boolean, nullable=False),
        timestamp("created_at"), timestamp("last_login_at", nullable=True),
        sa.Column("credential_version", sa.Integer, nullable=False),
    )
    op.create_table("journeys", identifier(),
        reference("vehicle_id", "vehicles.id"), reference("driver_id", "drivers.id"),
        sa.Column("route", sa.String(500), nullable=False),
        sa.Column("status", sa.String(16), nullable=False), timestamp("planned_at"),
        timestamp("started_at", nullable=True), timestamp("ended_at", nullable=True),
        sa.Column("progress", sa.Float, nullable=False),
        sa.Column("integrity", sa.String(32), nullable=False), timestamp("updated_at"),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="journey_progress_range"),
    )
    for field in ("vehicle_id", "driver_id"):
        op.create_index(f"ix_journeys_{field}", "journeys", [field])
        op.create_index(f"uq_live_journey_{field.removesuffix('_id')}", "journeys", [field], unique=True,
            postgresql_where=sa.text("status IN ('active', 'delayed')"),
            sqlite_where=sa.text("status IN ('active', 'delayed')"))
    op.create_table("driver_records", identifier(),
        reference("driver_id", "drivers.id"), reference("journey_id", "journeys.id"),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), timestamp("at"), timestamp("updated_at"),
    )
    for field in ("driver_id", "journey_id", "kind"):
        op.create_index(f"ix_driver_records_{field}", "driver_records", [field])
    op.create_table("shipments", identifier(), reference("journey_id", "journeys.id", nullable=True),
        sa.Column("status", sa.String(32), nullable=False), timestamp("updated_at"))
    for field in ("journey_id", "status"):
        op.create_index(f"ix_shipments_{field}", "shipments", [field])
    op.create_table("gnss_recordings", identifier(), reference("vehicle_id", "vehicles.id"),
        timestamp("recorded_at"), sa.Column("upload_state", sa.String(16), nullable=False),
        sa.Column("processing_state", sa.String(16), nullable=False), timestamp("updated_at"))
    for field in ("vehicle_id", "recorded_at", "upload_state", "processing_state"):
        op.create_index(f"ix_gnss_recordings_{field}", "gnss_recordings", [field])
    op.create_table("device_issues", identifier(), reference("vehicle_id", "vehicles.id"),
        sa.Column("kind", sa.String(32), nullable=False), sa.Column("device", sa.String(150), nullable=False),
        sa.Column("detail", sa.Text, nullable=False), timestamp("since"),
        timestamp("resolved_at", nullable=True), timestamp("updated_at"))
    op.create_index("ix_device_issues_vehicle_id", "device_issues", ["vehicle_id"])
    op.create_table("activity", identifier(), timestamp("at"),
        sa.Column("actor", sa.String(150), nullable=False), sa.Column("text", sa.Text, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False))
    for field in ("at", "kind"):
        op.create_index(f"ix_activity_{field}", "activity", [field])


def downgrade():
    for table in ("activity", "device_issues", "gnss_recordings", "shipments", "driver_records",
                  "journeys", "mobile_accounts", "vehicles", "drivers", "email_outbox",
                  "password_reset_tokens", "mfa_challenges", "access_sessions", "user_roles", "roles"):
        op.drop_table(table)
    with op.batch_alter_table("users") as batch:
        for column in ("locked_until", "failed_logins", "last_login", "mfa_enabled", "status"):
            batch.drop_column(column)
