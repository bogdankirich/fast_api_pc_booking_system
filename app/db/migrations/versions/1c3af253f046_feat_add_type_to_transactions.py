"""feat: add type to transactions

Revision ID: 1c3af253f046
Revises: 0d9796b69d2e
Create Date: 2026-05-26 13:37:06.062355

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1c3af253f046"
down_revision: Union[str, Sequence[str], None] = "0d9796b69d2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    transaction_type = postgresql.ENUM("DEPOSIT", "WITHDRAWAL", name="transactiontype")
    transaction_type.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "transactions",
        sa.Column(
            "type",
            sa.Enum("DEPOSIT", "WITHDRAWAL", name="transactiontype"),
            server_default="DEPOSIT",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "type")

    transaction_type = postgresql.ENUM("DEPOSIT", "WITHDRAWAL", name="transactiontype")
    transaction_type.drop(op.get_bind(), checkfirst=True)
