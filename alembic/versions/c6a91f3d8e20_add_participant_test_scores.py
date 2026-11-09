"""Add participant test scores.

Revision ID: c6a91f3d8e20
Revises: b83d42a1f607
"""

from alembic import op
import sqlalchemy as sa


revision = "c6a91f3d8e20"
down_revision = "b83d42a1f607"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "participant_test_scores",
        sa.Column("subject_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("rule_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("score", sa.Numeric(12, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["participants.subject_id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["questionnaire_scoring_rules.id"]),
        sa.PrimaryKeyConstraint("subject_id", "rule_id"),
    )


def downgrade() -> None:
    op.drop_table("participant_test_scores")
