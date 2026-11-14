"""initial syncore_employees

Revision ID: 20251114_001
Revises:
Create Date: 2025-11-14

"""

from alembic import op
import sqlalchemy as sa

revision = "20251114_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "syncore_employees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("employee_id", sa.String(length=50), nullable=False),
        sa.Column("signed_array", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("firm_id", sa.String(length=50), nullable=True),
        sa.Column("firm_name", sa.String(length=200), nullable=True),
        sa.Column("org_team_id", sa.String(length=50), nullable=True),
        sa.Column("org_name", sa.String(length=200), nullable=True),
        sa.Column("is_org_manager", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("designation", sa.String(length=200), nullable=True),
        sa.Column("user_type", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("team_lead_id", sa.String(length=50), nullable=True),
        sa.Column("team_lead_name", sa.String(length=200), nullable=True),
        sa.Column("reporting_time", sa.String(length=20), nullable=True),
        sa.Column("working_hours", sa.String(length=20), nullable=True),
        sa.Column("monthly_worklog_hours", sa.String(length=20), nullable=True),
        sa.Column("joining_date", sa.Date(), nullable=True),
        sa.Column("leaving_date", sa.Date(), nullable=True),
        sa.Column("training_completion_date", sa.Date(), nullable=True),
        sa.Column("comp_off", sa.String(length=20), nullable=True),
        sa.Column("emergency_leave", sa.String(length=20), nullable=True),
        sa.Column("casual_leave", sa.String(length=20), nullable=True),
        sa.Column("extended_leave", sa.String(length=20), nullable=True),
        sa.Column("syn_coin", sa.String(length=20), nullable=True),
        sa.Column("overrides", sa.String(length=20), nullable=True),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.Column("modified_by", sa.String(length=200), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id"),
    )
    op.create_index(op.f("ix_syncore_employees_user_id"), "syncore_employees", ["user_id"], unique=False)
    op.create_index(op.f("ix_syncore_employees_employee_id"), "syncore_employees", ["employee_id"], unique=True)
    op.create_index(op.f("ix_syncore_employees_name"), "syncore_employees", ["name"], unique=False)
    op.create_index(op.f("ix_syncore_employees_email"), "syncore_employees", ["email"], unique=False)
    op.create_index(op.f("ix_syncore_employees_firm_id"), "syncore_employees", ["firm_id"], unique=False)
    op.create_index(op.f("ix_syncore_employees_status"), "syncore_employees", ["status"], unique=False)
    op.create_index(op.f("ix_syncore_employees_joining_date"), "syncore_employees", ["joining_date"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_syncore_employees_joining_date"), table_name="syncore_employees")
    op.drop_index(op.f("ix_syncore_employees_status"), table_name="syncore_employees")
    op.drop_index(op.f("ix_syncore_employees_firm_id"), table_name="syncore_employees")
    op.drop_index(op.f("ix_syncore_employees_email"), table_name="syncore_employees")
    op.drop_index(op.f("ix_syncore_employees_name"), table_name="syncore_employees")
    op.drop_index(op.f("ix_syncore_employees_employee_id"), table_name="syncore_employees")
    op.drop_index(op.f("ix_syncore_employees_user_id"), table_name="syncore_employees")
    op.drop_table("syncore_employees")