from datetime import datetime
from typing import Annotated, Literal

from pydantic import EmailStr, Field, StringConstraints, field_validator, model_validator

from app.application.schemas import APIModel
from app.domain.authentication.permissions import PERMISSIONS

Name = Annotated[str, Field(min_length=2, max_length=150)]
RoleIds = Annotated[list[str], Field(min_length=1)]
UserStatus = Literal["active", "inactive", "pending"]


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)

    # Passwords are opaque; shared whitespace normalization must not alter them.
    model_config = {**APIModel.model_config, "str_strip_whitespace": False}


class SessionUser(APIModel):
    id: str
    name: str
    email: str


class SessionResponse(APIModel):
    token: str
    expires_at: datetime
    user: SessionUser
    role_names: list[str]
    permissions: list[str]


class UserInput(APIModel):
    name: Name
    email: EmailStr
    role_ids: RoleIds
    password: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(
        min_length=1, max_length=1024, repr=False, json_schema_extra={"writeOnly": True},
    )


class UserPatch(APIModel):
    name: Name | None = None
    email: EmailStr | None = None
    role_ids: RoleIds | None = None
    status: UserStatus | None = None

    @model_validator(mode="after")
    def reject_explicit_null(self):
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("User fields cannot be null.")
        return self


class UserResponse(APIModel):
    name: Name
    email: EmailStr
    role_ids: list[str]
    id: str
    status: UserStatus
    last_login: datetime | None


class RoleInput(APIModel):
    name: str = Field(min_length=3, max_length=150)
    description: str = Field(max_length=5000)
    permissions: list[str] = Field(min_length=1)

    @field_validator("permissions")
    @classmethod
    def valid_permissions(cls, value):
        if set(value) - PERMISSIONS:
            raise ValueError("Unknown permission key.")
        return sorted(set(value))


class RoleResponse(RoleInput):
    id: str
    built_in: bool
    locked_permissions: list[str]
    user_count: int
