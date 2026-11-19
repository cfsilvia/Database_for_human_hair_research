"""Add participant hair donation information."""

from alembic import op
import sqlalchemy as sa


revision = "e8c12a6f930b"
down_revision = "d99417bd520c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("participants", sa.Column("gave_hair", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("participants", "gave_hair")
