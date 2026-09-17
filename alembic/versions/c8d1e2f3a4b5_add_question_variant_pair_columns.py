"""add question variant pair columns

Revision ID: c8d1e2f3a4b5
Revises: b7c9d2e4f6a1
Create Date: 2026-09-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c8d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "b7c9d2e4f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        ALTER TABLE question_variants
        ADD COLUMN IF NOT EXISTS pair_status VARCHAR(20);
        """
    )
    op.execute(
        """
        ALTER TABLE question_variants
        ADD COLUMN IF NOT EXISTS pair_similarity DOUBLE PRECISION;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        ALTER TABLE question_variants
        DROP COLUMN IF EXISTS pair_similarity;
        """
    )
    op.execute(
        """
        ALTER TABLE question_variants
        DROP COLUMN IF EXISTS pair_status;
        """
    )
