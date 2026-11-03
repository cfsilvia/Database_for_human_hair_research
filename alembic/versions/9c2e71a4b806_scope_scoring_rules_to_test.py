"""Scope scoring rules to the psychological test.

Revision ID: 9c2e71a4b806
Revises: 7b405e4f6ebe
"""

from alembic import op
import sqlalchemy as sa


revision = "9c2e71a4b806"
down_revision = "7b405e4f6ebe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check uniqueness before removing the original questionnaire association.
    op.create_unique_constraint(
        "uq_test_scoring_rule",
        "questionnaire_scoring_rules",
        ["test_name", "rule_code"],
    )
    op.drop_constraint(
        "uq_questionnaire_scoring_rule",
        "questionnaire_scoring_rules",
        type_="unique",
    )
    op.drop_index(
        "ix_questionnaire_scoring_rules_questionnaire_id",
        table_name="questionnaire_scoring_rules",
    )
    op.drop_column("questionnaire_scoring_rules", "questionnaire_id")


def downgrade() -> None:
    # A rule spanning questionnaires has no single original questionnaire ID.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM questionnaire_scoring_rules) THEN
                RAISE EXCEPTION 'Cannot downgrade nonempty scoring rules: questionnaire associations must be restored explicitly.';
            END IF;
        END $$;
    """)
    op.add_column(
        "questionnaire_scoring_rules",
        sa.Column("questionnaire_id", sa.Integer(), nullable=False),
    )
    op.create_foreign_key(
        "questionnaire_scoring_rules_questionnaire_id_fkey",
        "questionnaire_scoring_rules",
        "questionnaires",
        ["questionnaire_id"],
        ["id"],
    )
    op.create_index(
        "ix_questionnaire_scoring_rules_questionnaire_id",
        "questionnaire_scoring_rules",
        ["questionnaire_id"],
    )
    op.drop_constraint(
        "uq_test_scoring_rule", "questionnaire_scoring_rules", type_="unique"
    )
    op.create_unique_constraint(
        "uq_questionnaire_scoring_rule",
        "questionnaire_scoring_rules",
        ["questionnaire_id", "test_name", "rule_code"],
    )
