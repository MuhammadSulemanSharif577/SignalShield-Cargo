"""Remove password recovery, email MFA, and the email outbox."""

from alembic import op
import sqlalchemy as sa

revision = "0002_remove_email_flows"
down_revision = "0001_frontend_contract"
branch_labels = None
depends_on = None


def upgrade():
    # Require a fresh password login for accounts previously using email MFA.
    op.execute(sa.text(
        "DELETE FROM access_sessions WHERE user_id IN "
        "(SELECT id FROM users WHERE mfa_enabled = true)"
    ))
    for table in ("email_outbox", "password_reset_tokens", "mfa_challenges"):
        op.drop_table(table)
    with op.batch_alter_table("users") as batch:
        batch.drop_column("mfa_enabled")


def downgrade():
    # Removed messages, tokens, and MFA enrollment cannot be recovered.
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("mfa_enabled", sa.Boolean, nullable=False, server_default=sa.false()))
    op.create_table("mfa_challenges",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
    )
    op.create_index("ix_mfa_challenges_user_id", "mfa_challenges", ["user_id"])
    op.create_table("password_reset_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_table("email_outbox",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
