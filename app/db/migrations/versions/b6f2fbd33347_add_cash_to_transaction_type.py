"""add_cash_to_transaction_type

Revision ID: b6f2fbd33347
Revises: 1c3af253f046
Create Date: 2026-06-12 13:56:55.526995

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6f2fbd33347"
down_revision: Union[str, Sequence[str], None] = "1c3af253f046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Изолируем команду от глобальной транзакции Alembic
    with op.get_context().autocommit_block():
        # IF NOT EXISTS защитит от ошибки, если тип уже случайно создался
        op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'CASH'")


def downgrade() -> None:
    pass
