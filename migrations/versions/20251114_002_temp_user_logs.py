"""temp user logs table

Revision ID: 20251114_002
Revises: 20251114_001
Create Date: 2025-11-14

"""

from alembic import op
import sqlalchemy as sa

revision = "20251114_002"
down_revision = "20251114_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "temp_user_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("synapse_user_id", sa.String(length=50), nullable=False),
        sa.Column("log_text", sa.Text(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_temp_user_logs_synapse_user_id"),
        "temp_user_logs",
        ["synapse_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_temp_user_logs_log_date"),
        "temp_user_logs",
        ["log_date"],
        unique=False,
    )
    op.create_index(
        "ix_temp_user_logs_user_date",
        "temp_user_logs",
        ["synapse_user_id", "log_date"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_temp_user_logs_user_date", table_name="temp_user_logs")
    op.drop_index(op.f("ix_temp_user_logs_log_date"), table_name="temp_user_logs")
    op.drop_index(op.f("ix_temp_user_logs_synapse_user_id"), table_name="temp_user_logs")
    op.drop_table("temp_user_logs")