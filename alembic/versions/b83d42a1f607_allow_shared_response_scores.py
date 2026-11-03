"""Allow answer options to share a score.

Revision ID: b83d42a1f607
Revises: 9c2e71a4b806
"""

from alembic import op


revision = "b83d42a1f607"
down_revision = "9c2e71a4b806"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_response_label_value", "response_value_labels", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_response_label_value", "response_value_labels", ["question_id", "numeric_value"]
    )
