from typing import Optional

import httpx
from aiogram.fsm.context import FSMContext


class APIClient:
    def __init__(self, base_url: str = "http://web:8000"):
        self.base_url = base_url
        self.timeout = 10.0

    async def _refresh_token(
        self, state: FSMContext, refresh_token: str
    ) -> Optional[str]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/refresh",
                    json={"refresh_token": refresh_token},
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    token_data = response.json()
                    new_access_token = token_data.get("access_token")
                    new_refresh_token = token_data.get("refresh_token")

                    await state.update_data(
                        access_token=new_access_token,
                        refresh_token=new_refresh_token,
                    )
                    return new_access_token

                return None

            except httpx.RequestError:
                return None

    async def request(
        self,
        method: str,
        endpoint: str,
        state: FSMContext,
        **kwargs,
    ) -> httpx.Response:
        user_data = await state.get_data()
        access_token = user_data.get("access_token")
        refresh_token = user_data.get("refresh_token")

        if not access_token:
            raise ValueError("User not authenticated")

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {access_token}"

        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method, url, headers=headers, timeout=self.timeout, **kwargs
            )

            if response.status_code == 401 and refresh_token:
                new_access_token = await self._refresh_token(state, refresh_token)

                if new_access_token:
                    headers["Authorization"] = f"Bearer {new_access_token}"
                    response = await client.request(
                        method, url, headers=headers, timeout=self.timeout, **kwargs
                    )
                else:
                    await state.clear()
                    raise ValueError("Token refresh failed, please login again")

            return response

    async def get(self, endpoint: str, state: FSMContext, **kwargs) -> httpx.Response:
        return await self.request("GET", endpoint, state, **kwargs)

    async def post(self, endpoint: str, state: FSMContext, **kwargs) -> httpx.Response:
        return await self.request("POST", endpoint, state, **kwargs)

    async def delete(
        self, endpoint: str, state: FSMContext, **kwargs
    ) -> httpx.Response:
        return await self.request("DELETE", endpoint, state, **kwargs)

    async def put(self, endpoint: str, state: FSMContext, **kwargs) -> httpx.Response:
        return await self.request("PUT", endpoint, state, **kwargs)
