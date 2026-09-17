"""align question metadata schema

Revision ID: 91f4c2d7a8b3
Revises: 632de54e226e
Create Date: 2026-09-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "91f4c2d7a8b3"
down_revision: Union[str, Sequence[str], None] = "632de54e226e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "canonical_questions",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        server_default=sa.text("now()"),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "participants",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        server_default=sa.text("now()"),
    )
    op.alter_column(
        "questionnaires",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        server_default=sa.text("now()"),
    )
    op.drop_constraint(
        "uq_question_variant",
        "question_variants",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_question_variant",
        "question_variants",
        [
            "questionnaire_id",
            "file_name",
            "question_number",
            "gender_form",
            "subquestion_phrase",
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_question_variant",
        "question_variants",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_question_variant",
        "question_variants",
        [
            "questionnaire_id",
            "question_number",
            "gender_form",
        ],
    )
    op.alter_column(
        "questionnaires",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        server_default=None,
    )
    op.alter_column(
        "participants",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        server_default=None,
    )
    op.alter_column(
        "canonical_questions",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=False,
        server_default=None,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
