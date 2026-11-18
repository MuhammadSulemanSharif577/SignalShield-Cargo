from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.authentication.use_cases.access_service import AccessService, Principal
from app.core.errors import APIError
from app.infrastructure.database.connection import get_db
from app.infrastructure.repositories.access_repository_implementation import SQLAlchemyAccessRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_access_service(db: Session = Depends(get_db)) -> AccessService:
    return AccessService(SQLAlchemyAccessRepository(db))


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    service: AccessService = Depends(get_access_service),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise APIError(401, "invalid_token", "A bearer session is required.")
    return service.authenticate(credentials.credentials)


def require_permissions(*permissions: str):
    def authorize(principal: Principal = Depends(get_current_user)) -> Principal:
        if not principal.can(*permissions):
            raise APIError(403, "forbidden", "You do not have permission to perform this operation.")
        return principal
    return authorize
