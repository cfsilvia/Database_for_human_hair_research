"""Add occupations and their classification groups."""

from alembic import op
import sqlalchemy as sa


revision = "f2a73c9d105e"
down_revision = "e8c12a6f930b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "occupations",
        sa.Column("occupation_code", sa.String(10), primary_key=True),
        sa.Column("occupation_he", sa.Text(), nullable=False),
        sa.Column("major_code", sa.String(10), nullable=False),
        sa.Column("major_group_he", sa.Text(), nullable=False),
        sa.Column("first_group_code", sa.String(10), nullable=False),
        sa.Column("first_group_he", sa.Text(), nullable=False),
        sa.Column("second_group_code", sa.String(10), nullable=False),
        sa.Column("second_group_he", sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table("occupations")
