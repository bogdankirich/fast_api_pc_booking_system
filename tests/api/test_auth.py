import pytest
from httpx import AsyncClient


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
