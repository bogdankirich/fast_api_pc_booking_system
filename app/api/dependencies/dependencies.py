from fastapi import Depends

from app.repositories.user import UserRepository
from app.services.user import UserService


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(user_repo=repo)
