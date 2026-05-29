from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transactions import Transaction, TransactionStatus, TransactionType
from app.models.user import User
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

    async def get_user_history(
        self, db: AsyncSession, user_id: int
    ) -> list[Transaction]:
        query = (
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def confirm_deposit_transaction(
        self, db: AsyncSession, transaction_id: str
    ) -> str:
        query = select(Transaction).where(Transaction.id == transaction_id)
        result = await db.execute(query)
        transaction = result.scalar_one_or_none()

        if not transaction:
            return "not_found"

        if transaction.status == TransactionStatus.SUCCESS:
            return "already_processed"

        user_query = select(User).where(User.id == transaction.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user:
            return "user_not_found"

        transaction.status = TransactionStatus.SUCCESS
        transaction.type = TransactionType.DEPOSIT

        user.balance += transaction.amount

        await db.commit()
        return "success"
