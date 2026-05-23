from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transactions import Transaction, TransactionStatus
from app.repositories.base import BaseRepository
from app.schemas.transaction import TopUpResponse


class TransactionRepository(BaseRepository[Transaction, TopUpResponse]):
    async def create_pending_transaction(
        self, db: AsyncSession, user_id: int, amount: Decimal
    ) -> Transaction:
        db_obj = Transaction(
            user_id=user_id, amount=amount, status=TransactionStatus.PENDING
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
