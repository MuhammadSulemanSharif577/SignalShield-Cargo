
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:

    id: int | None

    full_name: str

    email: str

    hashed_password: str

    is_active: bool = True

    created_at: datetime | None = None

    status: str = "active"
    last_login: datetime | None = None
    role_ids: list[str] = field(default_factory=list)
    failed_logins: int = 0
    locked_until: datetime | None = None
