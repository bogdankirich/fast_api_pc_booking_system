import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    await async_client.post(
        "/api/v1/users/",
        json={"email": "auth_test@gmail.com", "password": "superpassword"},
    )

    response = await async_client.post(
        "/api/v1/login",
        data={"username": "auth_test@gmail.com", "password": "superpassword"},
    )

    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient):
    await async_client.post(
        "/api/v1/users/",
        json={"email": "wrong_pass@gmail.com", "password": "correct_password"},
    )

    response = await async_client.post(
        "/api/v1/login",
        data={"username": "wrong_pass@gmail.com", "password": "WRONG_PASSWORD_123"},
    )
    assert response.status_code in (400, 401)


@pytest.mark.asyncio
@patch("app.api.endpoints.auth.oauth.google.authorize_redirect", new_callable=AsyncMock)
async def test_login_google_redirect(mock_redirect, async_client: AsyncClient):
    from starlette.responses import RedirectResponse

    mock_redirect.return_value = RedirectResponse(
        url="https://accounts.google.com/o/oauth2/v2/auth"
    )

    response = await async_client.get("/api/v1/login/google", follow_redirects=False)

    assert response.status_code in (302, 303, 307)
    assert mock_redirect.called


@pytest.mark.asyncio
@patch(
    "app.api.endpoints.auth.oauth.google.authorize_access_token", new_callable=AsyncMock
)
async def test_auth_google_callback_new_user(
    mock_authorize, async_client: AsyncClient, db: AsyncSession
):
    fake_email = "new_google_user@gmail.com"

    mock_authorize.return_value = {
        "access_token": "fake-google-token",
        "userinfo": {"email": fake_email, "name": "Test Google User"},
    }

    response = await async_client.get(
        "/api/v1/auth/google/callback?state=fakestate&code=fakecode"
    )

    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    result = await db.execute(select(User).where(User.email == fake_email))
    db_user = result.scalar_one_or_none()

    assert db_user is not None
    assert db_user.email == fake_email
    assert db_user.auth_provider == "google"
    assert db_user.hashed_password is None


@pytest.mark.asyncio
@patch(
    "app.api.endpoints.auth.oauth.google.authorize_access_token", new_callable=AsyncMock
)
async def test_auth_google_callback_existing_local_user(
    mock_authorize, async_client: AsyncClient
):
    local_email = "local_test_user@gmail.com"

    await async_client.post(
        "/api/v1/users/",
        json={"email": local_email, "password": "superpassword"},
    )

    mock_authorize.return_value = {
        "access_token": "fake-google-token",
        "userinfo": {"email": local_email},
    }

    response = await async_client.get(
        "/api/v1/auth/google/callback?state=fakestate&code=fakecode"
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_refresh_token_success(async_client: AsyncClient):
    email = "refresh_success@gmail.com"
    password = "superpassword"

    await async_client.post(
        "/api/v1/users/", json={"email": email, "password": password}
    )

    login_response = await async_client.post(
        "/api/v1/login", data={"username": email, "password": password}
    )
    old_refresh_token = login_response.json()["refresh_token"]

    await asyncio.sleep(1)

    refresh_response = await async_client.post(
        "/api/v1/refresh", json={"refresh_token": old_refresh_token}
    )

    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens

    assert new_tokens["refresh_token"] != old_refresh_token


@pytest.mark.asyncio
async def test_refresh_token_invalid_signature(async_client: AsyncClient):
    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.token"

    response = await async_client.post(
        "/api/v1/refresh", json={"refresh_token": fake_token}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_wrong_type(async_client: AsyncClient):
    email = "wrong_type@gmail.com"
    password = "superpassword"

    await async_client.post(
        "/api/v1/users/", json={"email": email, "password": password}
    )
    login_response = await async_client.post(
        "/api/v1/login", data={"username": email, "password": password}
    )

    access_token = login_response.json()["access_token"]

    refresh_response = await async_client.post(
        "/api/v1/refresh", json={"refresh_token": access_token}
    )

    assert refresh_response.status_code == 401
