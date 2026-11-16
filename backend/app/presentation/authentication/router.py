
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from app.application.authentication.schemas.auth_schemas import UserResponse
from app.presentation.authentication.dependencies import get_current_user
from app.core.config import settings
from app.core.security import create_access_token

from app.application.authentication.schemas.auth_schemas import (
    RegisterRequest,
    LoginRequest,
    AuthResponse
)

from app.application.authentication.use_cases.register_user import RegisterUser
from app.application.authentication.use_cases.login_user import LoginUser

from app.presentation.authentication.dependencies import (
    get_register_user,
    get_login_user
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# REGISTER USER

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED
)
def register(
    request: RegisterRequest,
    use_case: RegisterUser = Depends(get_register_user)
):

    try:

        user = use_case.execute(
            full_name=request.full_name,
            email=str(request.email),
            password=request.password
        )

        expires = timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

        token = create_access_token(
            user_id=user.id,
            expires_delta=expires
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": int(expires.total_seconds()),
            "user": user
        }

    except ValueError as error:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error)
        )


# LOGIN USER

@router.post(
    "/login",
    response_model=AuthResponse
)
def login(
    request: LoginRequest,
    use_case: LoginUser = Depends(get_login_user)
):

    try:

        user = use_case.execute(
            identifier=str(request.identifier),
            password=request.password
        )

        if request.remember_me:

            expires = timedelta(
                days=settings.REMEMBER_ME_EXPIRE_DAYS
            )

        else:

            expires = timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )

        token = create_access_token(
            user_id=user.id,
            expires_delta=expires
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": int(expires.total_seconds()),
            "user": user
        }

    except ValueError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )


# GET CURRENT AUTHENTICATED USER

@router.get(
    "/me",
    response_model=UserResponse
)
def get_me(
    current_user=Depends(get_current_user)
):

    return current_user
