from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.dependencies import get_current_user, get_user_service
from app.db.database import get_db_session
from app.models.transactions import Transaction, TransactionStatus
from app.models.user import User
from app.repositories.transaction import TransactionRepository
from app.schemas.transaction import (
    MonoBankWebhookRequest,
    TopUpRequest,
    TopUpResponse,
    TransactionHistoryResponse,
)
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.payment import MonoPayService
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db_session),
    user_service: UserService = Depends(get_user_service),
):
    try:
        new_user = await user_service.create_user(db=db, user_in=user_in)
        return new_user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_users_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    user_service: UserService = Depends(get_user_service),
):
    try:
        updated_user = await user_service.update_user(
            db=db, db_user=current_user, update_data=user_update
        )
        return updated_user
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/me/balance/top-up", response_model=TopUpResponse)
async def top_up_balance(
    request: TopUpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    transaction_repo = TransactionRepository(Transaction)
    transaction = await transaction_repo.create_pending_transaction(
        db=db, user_id=current_user.id, amount=request.amount
    )

    payment_service = MonoPayService()
    payment_url = await payment_service.create_invoice(
        amount=Decimal(request.amount),
        order_id=str(transaction.id),
        description=f"Пополнение баланса клуба. Пользователь: {current_user.email}",
    )
    if not payment_url:
        raise HTTPException(
            status_code=500,
            detail="Временно невозможно создать платеж. Сервис Монобанка недоступен.",
        )

    return TopUpResponse(transaction_id=str(transaction.id), payment_url=payment_url)


@router.post("/webhook/monobank", status_code=200)
async def monobank_webhook(
    webhook_data: MonoBankWebhookRequest, db: AsyncSession = Depends(get_db_session)
):
    query = select(Transaction).where(Transaction.id == webhook_data.reference)
    result = await db.execute(query)
    transaction = result.scalar_one_or_none()

    if not transaction:
        return {"status": "ignored"}

    if transaction.status == TransactionStatus.SUCCESS:
        return {"status": "already_processed"}

    if webhook_data.status == "success":
        user_query = select(User).where(User.id == transaction.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one()
        transaction.status = TransactionStatus.SUCCESS

        added_amount = Decimal(webhook_data.amount) / 100
        user.balance += added_amount

        await db.commit()
        return {"status": "success"}

    elif webhook_data.status in ["failure", "declined", "expired"]:
        transaction.status = TransactionStatus.FAILED
        await db.commit()
        return {"status": "failed"}

    return {"status": "pending"}


@router.get("/me/transactions", response_model=list[TransactionHistoryResponse])
async def get_user_transaction_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    transaction_repo = TransactionRepository(Transaction)
    return await transaction_repo.get_user_history(db, current_user.id)
