"""Save participant-specific AI occupation findings."""

from alembic import op
import sqlalchemy as sa


revision = "a3b84d0e216f"
down_revision = "f2a73c9d105e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "occupation_overrides",
        sa.Column("subject_id", sa.Integer(),
                  sa.ForeignKey("participants.subject_id"), primary_key=True),
        *[sa.Column(name, sa.Text(), nullable=False) for name in (
            "occupation_answer", "major_code", "major_group_he",
            "first_group_code", "first_group_he", "second_group_code",
            "second_group_he", "review", "source_filename",
        )],
    )


def downgrade():
    op.drop_table("occupation_overrides")
