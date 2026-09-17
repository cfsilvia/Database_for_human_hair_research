"""rename phrase_hebrew to question

Revision ID: b7c9d2e4f6a1
Revises: 91f4c2d7a8b3
Create Date: 2026-09-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b7c9d2e4f6a1"
down_revision: Union[str, Sequence[str], None] = "91f4c2d7a8b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'question_variants'
                  AND column_name = 'phrase_hebrew'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'question_variants'
                  AND column_name = 'question'
            ) THEN
                ALTER TABLE question_variants
                RENAME COLUMN phrase_hebrew TO question;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'question_variants'
                  AND column_name = 'question'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'question_variants'
                  AND column_name = 'phrase_hebrew'
            ) THEN
                ALTER TABLE question_variants
                RENAME COLUMN question TO phrase_hebrew;
            END IF;
        END $$;
        """
    )
