
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# REGISTRATION REQUEST

class RegisterRequest(BaseModel):

    full_name: str = Field(min_length=2, max_length=150)

    email: EmailStr

    password: str = Field(min_length=8, max_length=128)


# LOGIN REQUEST

class LoginRequest(BaseModel):

    identifier: EmailStr

    password: str = Field(min_length=1, max_length=128)

    remember_me: bool = False


# USER RESPONSE

class UserResponse(BaseModel):

    id: int

    full_name: str

    email: EmailStr

    model_config = ConfigDict(from_attributes=True)


# AUTHENTICATION RESPONSE

class AuthResponse(BaseModel):

    access_token: str

    token_type: str = "bearer"

    expires_in: int

    user: UserResponse
