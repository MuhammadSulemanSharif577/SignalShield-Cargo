import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from app.application.authentication.schemas.auth_schemas import (
    RoleInput, RoleResponse, SessionResponse, SessionUser,
    UserInput, UserPatch, UserResponse,
)
from app.core.config import settings
from app.core.errors import APIError
from app.core.security import hash_password, verify_password
from app.core.time import utcnow
from app.domain.authentication.entities.access import AccessSession, Role
from app.domain.authentication.entities.user import User
from app.domain.authentication.interfaces.access_repository import AccessRepository
from app.domain.authentication.permissions import DRIVER_ROLE_ID


def token_digest(token: str) -> str:
    return hmac.new(settings.JWT_SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()


def validate_password(password: str) -> None:
    if (len(password) < 10 or not re.search(r"[A-Z]", password)
            or not re.search(r"[a-z]", password) or not re.search(r"[0-9]", password)):
        raise APIError(422, "weak_password", "Use at least 10 characters, one uppercase letter, one lowercase letter, and one number.")


@dataclass
class Principal:
    user: User
    token_hash: str
    permissions: set[str]
    roles: list[Role]

    def can(self, *permissions: str) -> bool:
        return bool(self.permissions.intersection(permissions))


def user_response(user: User) -> UserResponse:
    return UserResponse(id=str(user.id), name=user.full_name, email=user.email,
                        role_ids=user.role_ids, status=user.status,
                        last_login=user.last_login, driver_id=user.driver_id,
                        must_change_password=user.must_change_password)


def session_user(user: User) -> SessionUser:
    return SessionUser(id=str(user.id), name=user.full_name, email=user.email,
                       driver_id=user.driver_id, must_change_password=user.must_change_password)


class AccessService:
    def __init__(self, repository: AccessRepository):
        self.repository = repository

    def _roles(self, user: User) -> list[Role]:
        return [role for role_id in sorted(user.role_ids)
                if (role := self.repository.get_role(role_id)) is not None]

    def _check_status(self, user: User) -> None:
        if user.status != "active":
            raise APIError(403, user.status, f"This account is {user.status}.")
        if user.driver_id and user.driver_status != "active":
            raise APIError(403, "inactive", "This driver is deactivated.")
        if user.locked_until and user.locked_until > utcnow():
            raise APIError(403, "locked", "This account is temporarily locked. Please try again later.")

    def authenticate(self, token: str) -> Principal:
        digest = token_digest(token)
        session = self.repository.get_session(digest)
        user = self.repository.get_by_id(session.user_id) if session else None
        if user is None or user.status != "active" or (user.driver_id and user.driver_status != "active"):
            raise APIError(401, "invalid_token", "Invalid, revoked, or expired session.")
        roles = self._roles(user)
        permissions = set() if user.must_change_password else {key for role in roles for key in role.permissions}
        return Principal(user, digest, permissions, roles)

    def _issue_session(self, user: User, *, record_login: bool = True) -> SessionResponse:
        token = secrets.token_urlsafe(48)
        expires = utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        self.repository.add_session(AccessSession(token_digest(token), user.id, expires))
        if record_login:
            user.last_login = utcnow()
            self.repository.save_user(user)
        roles = self._roles(user)
        result = SessionResponse(
            token=token, expires_at=expires,
            user=session_user(user),
            role_names=[role.name for role in roles],
            permissions=[] if user.must_change_password else sorted({key for role in roles for key in role.permissions}),
        )
        self.repository.commit()
        return result

    def login(self, email: str, password: str) -> SessionResponse:
        user = self.repository.get_by_email(email.strip().lower())
        if user is None:
            # Match the password-verification cost without exposing whether an email exists.
            verify_password(password, DUMMY_PASSWORD_HASH)
            raise APIError(401, "invalid_credentials", "Invalid email or password.")
        user = self.repository.lock_user(user.id)
        if user.locked_until and user.locked_until > utcnow():
            raise APIError(403, "locked", "This account is temporarily locked. Please try again later.")
        if not verify_password(password, user.hashed_password):
            if user.locked_until:
                user.failed_logins = 0
                user.locked_until = None
            user.failed_logins += 1
            if user.failed_logins >= settings.LOGIN_MAX_ATTEMPTS:
                user.locked_until = utcnow() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            self.repository.save_user(user)
            self.repository.commit()
            raise APIError(401, "invalid_credentials", "Invalid email or password.")
        self._check_status(user)
        user.failed_logins = 0
        user.locked_until = None
        self.repository.save_user(user)
        return self._issue_session(user)

    def refresh(self, principal: Principal) -> SessionResponse:
        user = self.repository.lock_user(principal.user.id)
        if user is None or user.status != "active" or not self.repository.consume_session(principal.token_hash):
            raise APIError(401, "invalid_token", "Invalid, revoked, or expired session.")
        return self._issue_session(user, record_login=False)

    def logout(self, principal: Principal) -> None:
        self.repository.consume_session(principal.token_hash)
        self.repository.commit()

    def change_password(self, principal: Principal, current_password: str, new_password: str) -> SessionResponse:
        validate_password(new_password)
        user = self.repository.lock_user(principal.user.id)
        if user is None or not self.repository.consume_session(principal.token_hash):
            raise APIError(401, "invalid_token", "Invalid, revoked, or expired session.")
        self._check_status(user)
        if not verify_password(current_password, user.hashed_password):
            raise APIError(422, "invalid_credentials", "The current password is incorrect.")
        if current_password == new_password:
            raise APIError(422, "validation", "Choose a different password.")
        user.hashed_password = hash_password(new_password)
        user.must_change_password = False
        user.failed_logins, user.locked_until = 0, None
        self.repository.save_user(user)
        self.repository.revoke_user_sessions(user.id)
        return self._issue_session(user, record_login=False)

    def list_users(self) -> list[UserResponse]:
        return [user_response(user) for user in self.repository.list_users()]

    def _validate_roles(self, role_ids: list[str]) -> list[str]:
        if DRIVER_ROLE_ID in role_ids:
            raise APIError(422, "validation", "Driver accounts are created and assigned their role from the driver profile.")
        for role_id in sorted(set(role_ids)):
            if self.repository.get_role(role_id, lock=True) is None:
                raise APIError(422, "validation", "One or more assigned roles do not exist.")
        return sorted(set(role_ids))

    def create_user(self, request: UserInput, principal: Principal) -> UserResponse:
        validate_password(request.password)
        email = str(request.email).lower()
        if self.repository.get_by_email(email):
            raise APIError(409, "conflict", "Email is already registered.")
        user = User(None, request.name, email, hash_password(request.password),
                    is_active=False, status="pending",
                    role_ids=self._validate_roles(request.role_ids))
        self.repository.save_user(user)
        self.repository.record_activity(principal.user.full_name, f"Created user {user.full_name}.")
        self.repository.commit()
        return user_response(user)

    def update_user(self, user_id: str, request: UserPatch, principal: Principal) -> UserResponse:
        try:
            identifier = int(user_id)
        except ValueError:
            raise APIError(404, "not_found", "User not found.")
        user = self.repository.lock_user(identifier)
        if user is None:
            raise APIError(404, "not_found", "User not found.")
        changes = request.model_dump(exclude_unset=True)
        if user.driver_id:
            if set(changes) - {"status"}:
                raise APIError(409, "conflict", "Edit linked driver details and credentials from the driver profile; its Driver role is fixed.")
            if changes.get("status") == "pending":
                raise APIError(422, "validation", "Linked driver accounts can only be active or inactive.")
            if changes.get("status") == "active" and user.driver_status != "active":
                raise APIError(409, "conflict", "Activate the driver profile before enabling its user account.")
        if user.id == principal.user.id and changes.get("status", user.status) != "active":
            raise APIError(409, "conflict", "You cannot deactivate your own account.")
        if "email" in changes:
            email = str(changes["email"]).lower()
            existing = self.repository.get_by_email(email)
            if existing and existing.id != user.id:
                raise APIError(409, "conflict", "Email is already registered.")
            user.email = email
        if "name" in changes:
            user.full_name = changes["name"]
        if "role_ids" in changes:
            user.role_ids = self._validate_roles(changes["role_ids"])
        if "status" in changes:
            user.status = changes["status"]
        if "email" in changes or user.status != "active":
            self.repository.revoke_user_sessions(user.id)
        self.repository.save_user(user)
        self.repository.record_activity(principal.user.full_name, f"Updated user {user.full_name}.")
        self.repository.commit()
        return user_response(user)

    def list_roles(self) -> list[RoleResponse]:
        return [RoleResponse.model_validate(role) for role in self.repository.list_roles()]

    def create_role(self, request: RoleInput, principal: Principal) -> RoleResponse:
        role = Role(str(uuid4()), request.name, request.description, request.permissions)
        self.repository.save_role(role)
        self.repository.record_activity(principal.user.full_name, f"Created role {role.name}.")
        self.repository.commit()
        return RoleResponse.model_validate(role)

    def update_role(self, role_id: str, request: RoleInput, principal: Principal) -> RoleResponse:
        if role_id == DRIVER_ROLE_ID:
            raise APIError(409, "conflict", "The built-in Driver role cannot be changed.")
        role = self.repository.get_role(role_id, lock=True)
        if role is None:
            raise APIError(404, "not_found", "Role not found.")
        if not set(role.locked_permissions).issubset(request.permissions):
            raise APIError(409, "conflict", "Protected role permissions cannot be removed.")
        role.name, role.description, role.permissions = request.name, request.description, request.permissions
        self.repository.save_role(role)
        self.repository.record_activity(principal.user.full_name, f"Updated role {role.name}.")
        self.repository.commit()
        return RoleResponse.model_validate(role)

    def delete_role(self, role_id: str, principal: Principal) -> None:
        role = self.repository.get_role(role_id, lock=True)
        if role is None:
            raise APIError(404, "not_found", "Role not found.")
        if role.built_in:
            raise APIError(409, "conflict", "Built-in roles cannot be deleted.")
        if role.user_count:
            raise APIError(409, "conflict", "An assigned role cannot be deleted.")
        self.repository.delete_role(role_id)
        self.repository.record_activity(principal.user.full_name, f"Deleted role {role.name}.")
        self.repository.commit()


DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))
