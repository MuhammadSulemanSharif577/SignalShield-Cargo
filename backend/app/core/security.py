
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from pwdlib import PasswordHash

from app.core.config import settings


password_hasher = PasswordHash.recommended()


# PASSWORD HASHING

def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:

    return password_hasher.verify(
        plain_password,
        hashed_password
    )


# JWT GENERATION

def create_access_token(
    user_id: int,
    expires_delta: timedelta
) -> str:

    now = datetime.now(timezone.utc)

    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": expire
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )

    return token


# JWT DECODING

def decode_access_token(token: str):

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        if payload.get("type") != "access":
            return None

        return payload

    except JWTError:
        return None
