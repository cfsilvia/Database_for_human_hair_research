"""Add war periods."""

from alembic import op
import sqlalchemy as sa


revision = "d7b02e4f9a31"
down_revision = "c6a91f3d8e20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "war_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.UniqueConstraint("name", name="uq_war_periods_name"),
    )


def downgrade() -> None:
    op.drop_table("war_periods")
