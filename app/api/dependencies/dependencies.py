import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ALGORITHM, SECRET_KEY
from app.db.database import get_db_session
from app.models.user import User
from app.repositories.booking import BookingRepository
from app.repositories.pc import PCRepository
from app.repositories.user import UserRepository
from app.repositories.zone import ZoneRepository
from app.services.booking import BookingService
from app.services.pc import PCService
from app.services.user import UserService
from app.services.zone import ZoneService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


def get_zone_repository() -> ZoneRepository:
    return ZoneRepository()


def get_pc_repository() -> PCRepository:
    return PCRepository()


def get_zone_service(
    repo: ZoneRepository = Depends(get_zone_repository),
) -> ZoneService:
    return ZoneService(zone_repo=repo)


def get_pc_service(
    pc_repo: PCRepository = Depends(get_pc_repository),
    zone_repo: ZoneRepository = Depends(get_zone_repository),
) -> PCService:
    return PCService(pc_repo=pc_repo, zone_repo=zone_repo)


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(user_repo=repo)


def get_booking_repository() -> BookingRepository:
    return BookingRepository()


def get_booking_service(
    booking_repo: BookingRepository = Depends(get_booking_repository),
    pc_repo: PCRepository = Depends(get_pc_repository),
    zone_repo: ZoneRepository = Depends(get_zone_repository),
) -> BookingService:
    return BookingService(
        booking_repo=booking_repo, pc_repo=pc_repo, zone_repo=zone_repo
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session),
    user_service: UserService = Depends(get_user_service),
) -> User:
    credentials_exeption = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Cannot confirm the credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise credentials_exeption
    except jwt.PyJWTError:
        raise credentials_exeption

    user = await user_service.user_repo.get_by_email(db, email=email)
    if user is None:
        raise credentials_exeption
    return user
