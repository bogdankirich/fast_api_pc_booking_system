import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import stripe
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transactions import TransactionStatus, TransactionType
from app.models.user import User
from tests.conftest import auth_headers, create_user_and_login


@pytest.mark.asyncio
async def test_top_up_balance_creates_checkout_session(
    async_client: AsyncClient, db: AsyncSession
):
    """Test successful checkout session creation for balance top-up."""
    token = await create_user_and_login(async_client, "topup@gmail.com")
    headers = auth_headers(token)

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/test_session_123"

    with patch(
        "stripe.checkout.Session.create_async", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_session

        response = await async_client.post(
            "/api/v1/users/me/balance/top-up",
            json={"amount": 100.50},
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "transaction_id" in data
    assert data["payment_url"] == "https://checkout.stripe.com/pay/test_session_123"

    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["payment_method_types"] == ["card"]
    assert call_kwargs["mode"] == "payment"
    assert call_kwargs["customer_email"] == "topup@gmail.com"
    assert call_kwargs["line_items"][0]["price_data"]["unit_amount"] == 10050


@pytest.mark.asyncio
async def test_top_up_balance_unauthorized(async_client: AsyncClient):
    """Test top-up endpoint rejects unauthenticated requests."""
    response = await async_client.post(
        "/api/v1/users/me/balance/top-up",
        json={"amount": 50.0},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_top_up_balance_stripe_service_unavailable(
    async_client: AsyncClient, db: AsyncSession
):
    """Test top-up endpoint handles Stripe service failures gracefully."""
    token = await create_user_and_login(async_client, "stripe_fail@gmail.com")
    headers = auth_headers(token)

    with patch(
        "stripe.checkout.Session.create_async", new_callable=AsyncMock
    ) as mock_create:
        mock_create.side_effect = stripe.StripeError("Service unavailable")

        response = await async_client.post(
            "/api/v1/users/me/balance/top-up",
            json={"amount": 200.0},
            headers=headers,
        )

    assert response.status_code == 500
    assert "Stripe недоступен" in response.json()["detail"]


@pytest.mark.asyncio
async def test_stripe_webhook_success_checkout_completed(
    async_client: AsyncClient, db: AsyncSession
):
    """Test webhook successfully processes checkout.session.completed event."""
    token = await create_user_and_login(async_client, "webhook_user@gmail.com")
    headers = auth_headers(token)

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/test"

    with patch(
        "stripe.checkout.Session.create_async", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_session
        top_up_response = await async_client.post(
            "/api/v1/users/me/balance/top-up",
            json={"amount": 150.0},
            headers=headers,
        )

    transaction_id = top_up_response.json()["transaction_id"]

    payload_bytes = b'{"fake": "payload"}'
    test_signature = "t=1234567890,v1=test_signature_hash"

    mock_session_stripe = MagicMock()
    mock_session_stripe.client_reference_id = transaction_id

    mock_event = MagicMock()
    mock_event.__getitem__.side_effect = lambda key: {
        "type": "checkout.session.completed",
        "data": {"object": mock_session_stripe},
    }[key]

    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = mock_event

        with patch(
            "app.tasks.telegram_notifications.send_payment_success_notification.delay"
        ):
            response = await async_client.post(
                "/api/v1/users/webhook/stripe",
                content=payload_bytes,
                headers={"stripe-signature": test_signature},
            )

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    from sqlalchemy import select

    from app.models.transactions import Transaction

    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    assert transaction is not None
    assert transaction.status == TransactionStatus.SUCCESS
    assert transaction.type == TransactionType.DEPOSIT

    user_result = await db.execute(
        select(User).where(User.email == "webhook_user@gmail.com")
    )
    user = user_result.scalar_one()
    assert user.balance == Decimal("150.0")


@pytest.mark.asyncio
async def test_stripe_webhook_missing_signature(async_client: AsyncClient):
    """Test webhook rejects requests without stripe-signature header."""
    payload_bytes = b'{"type": "checkout.session.completed"}'

    response = await async_client.post(
        "/api/v1/users/webhook/stripe",
        content=payload_bytes,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing signature header"


@pytest.mark.asyncio
async def test_stripe_webhook_invalid_signature(async_client: AsyncClient):
    """Test webhook rejects requests with invalid signature."""
    payload_bytes = b'{"type": "checkout.session.completed"}'
    invalid_signature = "t=1234567890,v1=invalid_signature"

    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.side_effect = stripe.SignatureVerificationError(
            "Invalid signature", invalid_signature
        )

        response = await async_client.post(
            "/api/v1/users/webhook/stripe",
            content=payload_bytes,
            headers={"stripe-signature": invalid_signature},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid signature"


@pytest.mark.asyncio
async def test_stripe_webhook_invalid_payload(async_client: AsyncClient):
    """Test webhook rejects malformed payload."""
    invalid_payload = b"not a valid json payload"
    test_signature = "t=1234567890,v1=test_signature"

    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.side_effect = ValueError("Invalid payload")

        response = await async_client.post(
            "/api/v1/users/webhook/stripe",
            content=invalid_payload,
            headers={"stripe-signature": test_signature},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid payload"


@pytest.mark.asyncio
async def test_stripe_webhook_missing_client_reference_id(async_client: AsyncClient):
    """Test webhook handles missing client_reference_id gracefully."""

    payload_bytes = b'{"fake": "payload"}'
    test_signature = "t=1234567890,v1=test_signature_hash"

    mock_session_stripe = MagicMock()
    mock_session_stripe.client_reference_id = None

    mock_event = MagicMock()
    mock_event.__getitem__.side_effect = lambda key: {
        "type": "checkout.session.completed",
        "data": {
            "object": mock_session_stripe  #
        },
    }[key]

    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = mock_event

        response = await async_client.post(
            "/api/v1/users/webhook/stripe",
            content=payload_bytes,
            headers={"stripe-signature": test_signature},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "missing_reference"


@pytest.mark.asyncio
async def test_stripe_webhook_nonexistent_transaction(async_client: AsyncClient):
    """Test webhook handles nonexistent transaction ID."""
    fake_transaction_id = str(uuid.uuid4())

    payload_bytes = b'{"fake": "payload"}'
    test_signature = "t=1234567890,v1=test_signature_hash"

    mock_session_stripe = MagicMock()
    mock_session_stripe.client_reference_id = fake_transaction_id

    mock_event = MagicMock()
    mock_event.__getitem__.side_effect = lambda key: {
        "type": "checkout.session.completed",
        "data": {"object": mock_session_stripe},
    }[key]

    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = mock_event

        response = await async_client.post(
            "/api/v1/users/webhook/stripe",
            content=payload_bytes,
            headers={"stripe-signature": test_signature},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "not_found"


@pytest.mark.asyncio
async def test_stripe_webhook_already_processed_transaction(
    async_client: AsyncClient, db: AsyncSession
):
    """Test webhook handles duplicate webhook events (idempotency)."""
    token = await create_user_and_login(async_client, "duplicate_webhook@gmail.com")
    headers = auth_headers(token)

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/test"

    with patch(
        "stripe.checkout.Session.create_async", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_session
        top_up_response = await async_client.post(
            "/api/v1/users/me/balance/top-up",
            json={"amount": 75.0},
            headers=headers,
        )

    transaction_id = top_up_response.json()["transaction_id"]

    payload_bytes = b'{"fake": "payload"}'
    test_signature = "t=1234567890,v1=test_signature_hash"

    mock_session_stripe = MagicMock()
    mock_session_stripe.client_reference_id = transaction_id

    mock_event = MagicMock()
    mock_event.__getitem__.side_effect = lambda key: {
        "type": "checkout.session.completed",
        "data": {"object": mock_session_stripe},
    }[key]

    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = mock_event

        with patch(
            "app.tasks.telegram_notifications.send_payment_success_notification.delay"
        ):
            first_response = await async_client.post(
                "/api/v1/users/webhook/stripe",
                content=payload_bytes,
                headers={"stripe-signature": test_signature},
            )

            second_response = await async_client.post(
                "/api/v1/users/webhook/stripe",
                content=payload_bytes,
                headers={"stripe-signature": test_signature},
            )

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "success"

    assert second_response.status_code == 200
    assert second_response.json()["status"] == "already_processed"

    from sqlalchemy import select

    from app.models.user import User

    user_result = await db.execute(
        select(User).where(User.email == "duplicate_webhook@gmail.com")
    )
    user = user_result.scalar_one()
    assert user.balance == Decimal("75.0")


@pytest.mark.asyncio
async def test_stripe_webhook_ignores_other_event_types(async_client: AsyncClient):
    """Test webhook ignores non-checkout.session.completed events."""
    payload_bytes = b'{"fake": "payload"}'
    test_signature = "t=1234567890,v1=test_signature"

    mock_event = MagicMock()
    mock_event.__getitem__.side_effect = lambda key: {
        "type": "payment_intent.succeeded",
        "data": {"object": MagicMock()},
    }[key]

    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = mock_event

        response = await async_client.post(
            "/api/v1/users/webhook/stripe",
            content=payload_bytes,
            headers={"stripe-signature": test_signature},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_stripe_webhook_does_not_send_notification_without_telegram_id(
    async_client: AsyncClient, db: AsyncSession
):
    """Test webhook doesn't send Telegram notification if user has no telegram_id."""
    token = await create_user_and_login(async_client, "no_telegram@gmail.com")
    headers = auth_headers(token)

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/test"

    with patch(
        "stripe.checkout.Session.create_async", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_session
        top_up_response = await async_client.post(
            "/api/v1/users/me/balance/top-up",
            json={"amount": 50.0},
            headers=headers,
        )

    transaction_id = top_up_response.json()["transaction_id"]

    payload_bytes = b'{"fake": "payload"}'
    test_signature = "t=1234567890,v1=test_signature_hash"

    mock_session_stripe = MagicMock()
    mock_session_stripe.client_reference_id = transaction_id

    mock_event = MagicMock()
    mock_event.__getitem__.side_effect = lambda key: {
        "type": "checkout.session.completed",
        "data": {"object": mock_session_stripe},
    }[key]

    with patch("stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = mock_event

        with patch(
            "app.tasks.telegram_notifications.send_payment_success_notification.delay"
        ) as mock_celery_task:
            response = await async_client.post(
                "/api/v1/users/webhook/stripe",
                content=payload_bytes,
                headers={"stripe-signature": test_signature},
            )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_celery_task.assert_not_called()
