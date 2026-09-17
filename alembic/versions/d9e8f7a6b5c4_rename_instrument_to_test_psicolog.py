"""rename instrument to test_psicolog

Revision ID: d9e8f7a6b5c4
Revises: c8d1e2f3a4b5
Create Date: 2026-09-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d9e8f7a6b5c4"
down_revision: Union[str, Sequence[str], None] = "c8d1e2f3a4b5"
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
                WHERE table_name = 'canonical_questions'
                  AND column_name = 'instrument'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'canonical_questions'
                  AND column_name = 'test_psicolog'
            ) THEN
                ALTER TABLE canonical_questions
                RENAME COLUMN instrument TO test_psicolog;
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
                WHERE table_name = 'canonical_questions'
                  AND column_name = 'test_psicolog'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'canonical_questions'
                  AND column_name = 'instrument'
            ) THEN
                ALTER TABLE canonical_questions
                RENAME COLUMN test_psicolog TO instrument;
            END IF;
        END $$;
        """
    )
