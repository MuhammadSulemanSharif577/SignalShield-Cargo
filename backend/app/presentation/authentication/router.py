from fastapi import APIRouter, Depends, Response

from app.application.authentication.schemas.auth_schemas import (
    LoginRequest, SessionResponse,
)
from app.application.authentication.use_cases.access_service import AccessService, Principal
from app.presentation.authentication.dependencies import get_access_service, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=SessionResponse)
def login(request: LoginRequest, service: AccessService = Depends(get_access_service)):
    return service.login(str(request.email), request.password)


@router.post("/refresh", response_model=SessionResponse)
def refresh(principal: Principal = Depends(get_current_user), service: AccessService = Depends(get_access_service)):
    return service.refresh(principal)


@router.post("/logout", status_code=204)
def logout(principal: Principal = Depends(get_current_user), service: AccessService = Depends(get_access_service)):
    service.logout(principal)
    return Response(status_code=204)
