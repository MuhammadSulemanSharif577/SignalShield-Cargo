from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Role:
    id: str
    name: str
    description: str
    permissions: list[str]
    built_in: bool = False
    locked_permissions: list[str] = field(default_factory=list)
    user_count: int = 0


@dataclass
class AccessSession:
    token_hash: str
    user_id: int
    expires_at: datetime
