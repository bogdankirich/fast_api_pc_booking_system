from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_user(self, db: AsyncSession, user_in: UserCreate) -> User:
        existing_user = await self.user_repo.get_by_email(db, email=user_in.email)
        if existing_user:
            if existing_user.auth_provider == "google":
                raise ValueError(
                    "This email is registered via Google. Please log in using Google."
                )
            raise ValueError("User with this email already existing")
        user_data = user_in.model_dump(exclude={"password"})
        user_data["hashed_password"] = get_password_hash(user_in.password)

        db_obj = User(**user_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_user(self, db: AsyncSession, user_id: int) -> User | None:
        return await self.user_repo.get(db, id=user_id)

    async def authenticate_user(
        self, db: AsyncSession, email: str, password: str
    ) -> User | None:
        user = await self.user_repo.get_by_email(db, email=email)
        if not user:
            return None
        if user.hashed_password is None:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def get_or_create_google_user(self, db: AsyncSession, email: str) -> User:
        user = await self.user_repo.get_by_email(db, email=email)
        if user:
            return user

        user_data = {"email": email, "auth_provider": "google", "hashed_password": None}

        db_obj = User(**user_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
