from dataclasses import dataclass
from datetime import datetime


@dataclass
class Vehicle:
    id: str
    registration: str
    type: str
    model: str
    status: str
    driver_id: str | None = None
    receiver_id: str | None = None
    device: dict | None = None
    last_location: dict | None = None
    updated_at: datetime | None = None


@dataclass
class Driver:
    id: str
    name: str
    phone: str
    email: str
    status: str = "active"
    user_account: dict | None = None
    vehicle_id: str | None = None
    updated_at: datetime | None = None


@dataclass
class Journey:
    id: str
    vehicle_id: str
    driver_id: str
    route: str
    status: str
    planned_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    driver_name: str | None = None
    vehicle_registration: str | None = None
    progress: float = 0
    integrity: str = "not_assessed"
    updated_at: datetime | None = None
