
from fastapi import Depends
from sqlalchemy.orm import Session

from app.infrastructure.database.connection import get_db
from app.infrastructure.repositories.user_repository_implementation import (
    SQLAlchemyUserRepository
)

from app.application.authentication.use_cases.register_user import RegisterUser
from app.application.authentication.use_cases.login_user import LoginUser
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token

def get_user_repository(
    db: Session = Depends(get_db)
):
    return SQLAlchemyUserRepository(db)


def get_register_user(
    repository=Depends(get_user_repository)
):
    return RegisterUser(repository)


def get_login_user(
    repository=Depends(get_user_repository)
):
    return LoginUser(repository)



# JWT BEARER AUTHENTICATION

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    repository=Depends(get_user_repository)
):

    token = credentials.credentials

    payload = decode_access_token(token)

    if payload is None:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("sub")

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token."
        )

    user = repository.get_by_id(user_id)

    if user is None or not user.is_active:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive."
        )

    return user
