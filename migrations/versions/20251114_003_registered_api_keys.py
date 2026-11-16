"""registered api keys and otps

Revision ID: 20251114_003
Revises: 20251114_002
Create Date: 2025-11-14

"""

from alembic import op
import sqlalchemy as sa

revision = "20251114_003"
down_revision = "20251114_002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "registered_api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("synapse_user_id", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(
        op.f("ix_registered_api_keys_synapse_user_id"),
        "registered_api_keys",
        ["synapse_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_registered_api_keys_email"),
        "registered_api_keys",
        ["email"],
        unique=False,
    )

    op.create_table(
        "registration_otps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("synapse_user_id", sa.String(length=50), nullable=False),
        sa.Column("otp_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_registration_otps_email"),
        "registration_otps",
        ["email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_registration_otps_synapse_user_id"),
        "registration_otps",
        ["synapse_user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_registration_otps_synapse_user_id"), table_name="registration_otps")
    op.drop_index(op.f("ix_registration_otps_email"), table_name="registration_otps")
    op.drop_table("registration_otps")
    op.drop_index(op.f("ix_registered_api_keys_email"), table_name="registered_api_keys")
    op.drop_index(op.f("ix_registered_api_keys_synapse_user_id"), table_name="registered_api_keys")
    op.drop_table("registered_api_keys")