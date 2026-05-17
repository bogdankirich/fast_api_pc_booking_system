from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext

from tg_bot.utils.api_client import APIClient


@pytest.mark.asyncio
async def test_api_client_get_with_valid_token(
    authenticated_fsm_context: FSMContext,
) -> None:
    api_client = APIClient(base_url="http://test:8000")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": "test"}

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request.return_value = mock_response
    mock_httpx_client.__aenter__.return_value = mock_httpx_client
    mock_httpx_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_httpx_client):
        response = await api_client.get("/api/test", authenticated_fsm_context)

    assert response.status_code == 200
    assert response.json() == {"data": "test"}

    mock_httpx_client.request.assert_called_once()
    call_args = mock_httpx_client.request.call_args
    assert call_args[0][0] == "GET"
    assert call_args[0][1] == "http://test:8000/api/test"
    assert call_args[1]["headers"]["Authorization"] == "Bearer test_access_token"


@pytest.mark.asyncio
async def test_api_client_post_with_json_data(
    authenticated_fsm_context: FSMContext,
) -> None:
    api_client = APIClient()

    mock_response = MagicMock()
    mock_response.status_code = 201

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request.return_value = mock_response
    mock_httpx_client.__aenter__.return_value = mock_httpx_client
    mock_httpx_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_httpx_client):
        response = await api_client.post(
            "/api/bookings",
            authenticated_fsm_context,
            json={"pc_id": 1, "duration": 60},
        )

    assert response.status_code == 201

    call_args = mock_httpx_client.request.call_args
    assert call_args[1]["json"] == {"pc_id": 1, "duration": 60}


@pytest.mark.asyncio
async def test_api_client_raises_error_without_token(fsm_context: FSMContext) -> None:
    api_client = APIClient()

    with pytest.raises(ValueError, match="User not authenticated"):
        await api_client.get("/api/test", fsm_context)


@pytest.mark.asyncio
async def test_api_client_refreshes_token_on_401(
    authenticated_fsm_context: FSMContext,
) -> None:
    api_client = APIClient()

    mock_401_response = MagicMock()
    mock_401_response.status_code = 401

    mock_200_response = MagicMock()
    mock_200_response.status_code = 200
    mock_200_response.json.return_value = {"data": "success"}

    mock_refresh_response = MagicMock()
    mock_refresh_response.status_code = 200
    mock_refresh_response.json.return_value = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
    }

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request.side_effect = [mock_401_response, mock_200_response]
    mock_httpx_client.post.return_value = mock_refresh_response
    mock_httpx_client.__aenter__.return_value = mock_httpx_client
    mock_httpx_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_httpx_client):
        response = await api_client.get("/api/test", authenticated_fsm_context)

    assert response.status_code == 200

    user_data = await authenticated_fsm_context.get_data()
    assert user_data["access_token"] == "new_access_token"
    assert user_data["refresh_token"] == "new_refresh_token"

    assert mock_httpx_client.request.call_count == 2


@pytest.mark.asyncio
async def test_api_client_clears_state_on_refresh_failure(
    authenticated_fsm_context: FSMContext,
) -> None:
    api_client = APIClient()

    mock_401_response = MagicMock()
    mock_401_response.status_code = 401

    mock_refresh_response = MagicMock()
    mock_refresh_response.status_code = 401

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request.return_value = mock_401_response
    mock_httpx_client.post.return_value = mock_refresh_response
    mock_httpx_client.__aenter__.return_value = mock_httpx_client
    mock_httpx_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_httpx_client):
        with pytest.raises(ValueError, match="Token refresh failed"):
            await api_client.get("/api/test", authenticated_fsm_context)

    user_data = await authenticated_fsm_context.get_data()
    assert user_data == {}


@pytest.mark.asyncio
async def test_api_client_delete_method(authenticated_fsm_context: FSMContext) -> None:
    api_client = APIClient()

    mock_response = MagicMock()
    mock_response.status_code = 204

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request.return_value = mock_response
    mock_httpx_client.__aenter__.return_value = mock_httpx_client
    mock_httpx_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_httpx_client):
        response = await api_client.delete("/api/bookings/1", authenticated_fsm_context)

    assert response.status_code == 204

    call_args = mock_httpx_client.request.call_args
    assert call_args[0][0] == "DELETE"


@pytest.mark.asyncio
async def test_api_client_put_method(authenticated_fsm_context: FSMContext) -> None:
    api_client = APIClient()

    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request.return_value = mock_response
    mock_httpx_client.__aenter__.return_value = mock_httpx_client
    mock_httpx_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_httpx_client):
        response = await api_client.put(
            "/api/users/me", authenticated_fsm_context, json={"name": "New Name"}
        )

    assert response.status_code == 200

    call_args = mock_httpx_client.request.call_args
    assert call_args[0][0] == "PUT"
