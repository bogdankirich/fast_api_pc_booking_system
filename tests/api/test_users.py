import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_new_user(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/users/",
        json={"email": "test_api@gmail.com", "password": "super_secure_password"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test_api@gmail.com"
    assert "id" in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_user_fails(async_client: AsyncClient):
    await async_client.post(
        "/api/v1/users/", json={"email": "clone@gmail.com", "password": "password123"}
    )

    response = await async_client.post(
        "/api/v1/users/", json={"email": "clone@gmail.com", "password": "password123"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "User with this email already existing"
