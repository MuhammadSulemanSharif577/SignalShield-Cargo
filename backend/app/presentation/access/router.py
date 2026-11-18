from fastapi import APIRouter, Depends, Response

from app.application.authentication.schemas.auth_schemas import RoleInput, RoleResponse, UserInput, UserPatch, UserResponse
from app.application.authentication.use_cases.access_service import AccessService, Principal
from app.presentation.authentication.dependencies import get_access_service, require_permissions

router = APIRouter(tags=["Users and roles"])


@router.get("/users", response_model=list[UserResponse])
def list_users(principal: Principal = Depends(require_permissions("users:view", "users:manage")),
               service: AccessService = Depends(get_access_service)):
    return service.list_users()


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(request: UserInput, principal: Principal = Depends(require_permissions("users:manage")),
                service: AccessService = Depends(get_access_service)):
    return service.create_user(request, principal)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: str, request: UserPatch,
                principal: Principal = Depends(require_permissions("users:manage")),
                service: AccessService = Depends(get_access_service)):
    return service.update_user(user_id, request, principal)


@router.get("/roles", response_model=list[RoleResponse])
def list_roles(principal: Principal = Depends(require_permissions("roles:manage", "users:view", "users:manage")),
               service: AccessService = Depends(get_access_service)):
    return service.list_roles()


@router.post("/roles", response_model=RoleResponse, status_code=201)
def create_role(request: RoleInput, principal: Principal = Depends(require_permissions("roles:manage")),
                service: AccessService = Depends(get_access_service)):
    return service.create_role(request, principal)


@router.put("/roles/{role_id}", response_model=RoleResponse)
def update_role(role_id: str, request: RoleInput,
                principal: Principal = Depends(require_permissions("roles:manage")),
                service: AccessService = Depends(get_access_service)):
    return service.update_role(role_id, request, principal)


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(role_id: str, principal: Principal = Depends(require_permissions("roles:manage")),
                service: AccessService = Depends(get_access_service)):
    service.delete_role(role_id, principal)
    return Response(status_code=204)
