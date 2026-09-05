"""add roles and ticket ownership

Revision ID: 92a1515994cb
Revises: 6e28f857f8d9
Create Date: 2026-08-13 19:34:31.308827

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92a1515994cb'
down_revision: Union[str, Sequence[str], None] = '6e28f857f8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.Enum(
                "EMPLOYEE",
                "SUPPORT_ENGINEER",
                "ADMIN",
                name="user_role",
                native_enum=False,
                create_constraint=False,
            ),
            server_default="EMPLOYEE",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('EMPLOYEE', 'SUPPORT_ENGINEER', 'ADMIN')",
    )
    op.add_column(
        "tickets",
        sa.Column("requester_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE tickets
        SET requester_id = (SELECT id FROM users ORDER BY id LIMIT 1)
        WHERE requester_id IS NULL
        """
    )
    op.alter_column("tickets", "requester_id", nullable=False)
    op.create_index(
        op.f("ix_tickets_requester_id"),
        "tickets",
        ["requester_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_tickets_requester_id_users",
        "tickets",
        "users",
        ["requester_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_tickets_requester_id_users",
        "tickets",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_tickets_requester_id"), table_name="tickets")
    op.drop_column("tickets", "requester_id")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
