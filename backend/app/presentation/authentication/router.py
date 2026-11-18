from fastapi import APIRouter, Depends, Response

from app.application.authentication.schemas.auth_schemas import (
    ChangePasswordRequest, LoginRequest, SessionResponse, SessionUser,
)
from app.application.authentication.use_cases.access_service import AccessService, Principal, session_user
from app.presentation.authentication.dependencies import get_access_service, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=SessionResponse)
def login(request: LoginRequest, service: AccessService = Depends(get_access_service)):
    return service.login(str(request.email), request.password)


@router.get("/me", response_model=SessionUser)
def me(principal: Principal = Depends(get_current_user)):
    return session_user(principal.user)


@router.post("/change-password", response_model=SessionResponse)
def change_password(request: ChangePasswordRequest, principal: Principal = Depends(get_current_user),
                    service: AccessService = Depends(get_access_service)):
    return service.change_password(principal, request.current_password, request.new_password)


@router.post("/refresh", response_model=SessionResponse)
def refresh(principal: Principal = Depends(get_current_user), service: AccessService = Depends(get_access_service)):
    return service.refresh(principal)


@router.post("/logout", status_code=204)
def logout(principal: Principal = Depends(get_current_user), service: AccessService = Depends(get_access_service)):
    service.logout(principal)
    return Response(status_code=204)
