import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.dependencies import get_current_user, get_user_service
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.database import get_db_session
from app.models.transactions import Transaction
from app.models.user import User
from app.repositories.transaction import TransactionRepository
from app.schemas.transaction import (
    TopUpRequest,
    TopUpResponse,
    TransactionHistoryResponse,
)
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.payment import StripePayService
from app.services.user import UserService
from app.tasks.telegram_notifications import send_payment_success_notification

router = APIRouter(prefix="/users", tags=["Users"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register_user(
    request: Request,
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
@limiter.limit("30/minute")
async def read_users_me(
    request: Request, current_user: User = Depends(get_current_user)
):
    return current_user


@router.patch("/me", response_model=UserResponse)
@limiter.limit("10/minute")
async def update_users_me(
    request: Request,
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
@limiter.limit("5/minute")
async def top_up_balance(
    request: Request,
    payload: TopUpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):

    transaction_repo = TransactionRepository(Transaction)
    transaction = await transaction_repo.create_pending_transaction(
        db=db, user_id=current_user.id, amount=payload.amount
    )

    payment_service = StripePayService()
    payment_url = await payment_service.create_checkout_session(
        amount=payload.amount,
        transaction_id=str(transaction.id),
        user_email=current_user.email,
    )

    if not payment_url:
        raise HTTPException(
            status_code=500,
            detail="Временно невозможно создать платеж. Сервис Stripe недоступен.",
        )

    return TopUpResponse(transaction_id=str(transaction.id), payment_url=payment_url)


@router.post("/webhook/stripe", status_code=200)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db_session)):
    payload = await request.body()
    stripe_signature = request.headers.get("stripe-signature")

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.warning("Stripe Webhook: Invalid payload received")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        logger.warning("Stripe Webhook: Invalid signature received")
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        transaction_id = session.client_reference_id

        if not transaction_id:
            return {"status": "missing_reference"}

        transaction_repo = TransactionRepository(Transaction)

        (
            result_status,
            tg_id,
            amount,
        ) = await transaction_repo.confirm_deposit_transaction(db, transaction_id)

        if result_status == "success" and tg_id:
            send_payment_success_notification.delay(tg_id, amount)  # type: ignore

        return {"status": result_status}

    return {"status": "ignored"}


@router.get("/me/transactions", response_model=list[TransactionHistoryResponse])
@limiter.limit("30/minute")
async def get_user_transaction_history(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    transaction_repo = TransactionRepository(Transaction)
    return await transaction_repo.get_user_history(db, current_user.id)
