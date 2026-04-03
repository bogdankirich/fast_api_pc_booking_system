from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.user import UserCreate


class UserRepository(BaseRepository[User, UserCreate]):
    def __init__(self) -> None:
        super().__init__(User)

    async def get_by_email(self, db: AsyncSession, *, email: str) -> User | None:
        query = select(self.model).where(self.model.email == email)
        result = await db.execute(query)
        return result.scalars().first()
