"""store encrypted OTP used at registration for admin UI

Revision ID: 20251116_005
Revises: 20251116_004
Create Date: 2025-11-16

"""

from alembic import op
import sqlalchemy as sa

revision = "20251116_005"
down_revision = "20251116_004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("registered_api_keys", schema=None) as batch_op:
        batch_op.add_column(sa.Column("otp_ciphertext", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("registered_api_keys", schema=None) as batch_op:
        batch_op.drop_column("otp_ciphertext")