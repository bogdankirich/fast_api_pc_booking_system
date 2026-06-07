from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.db.database import async_session_maker
from app.repositories.user import UserRepository
from app.services.user import UserService


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = form.get("username")
        password = form.get("password")

        if not isinstance(email, str) or not isinstance(password, str):
            return False

        async with async_session_maker() as db:
            user_service = UserService(UserRepository())
            user = await user_service.authenticate_user(db, email, password)

            if user and user.role == "admin":
                request.session.update({"token": str(user.id)})
                return True

        return False

    async def logout(self, request: Request) -> bool:

        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:

        token = request.session.get("token")
        return token is not None
