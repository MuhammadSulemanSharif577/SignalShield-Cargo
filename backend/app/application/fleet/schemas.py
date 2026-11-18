from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.application.schemas import APIModel

VehicleStatus = Literal["active", "inactive", "maintenance", "unavailable"]
DriverStatus = Literal["active", "inactive"]
Severity = Literal["critical", "high", "medium", "low"]


class VehicleInput(APIModel):
    registration: str = Field(min_length=4, max_length=12, pattern=r"^[A-Z0-9][A-Z0-9 -]{3,11}$")
    type: Literal["truck", "van", "pickup", "reefer"]
    model: str = Field(min_length=2, max_length=150)
    status: VehicleStatus
    receiver_id: str = Field(max_length=150)

    @field_validator("registration", mode="before")
    @classmethod
    def normalize_registration(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class DriverInput(APIModel):
    name: str = Field(min_length=2, max_length=150)
    phone: str = Field(pattern=r"^\+?[\d\s-]{7,16}$")
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return value.lower()


class VehicleStatusInput(APIModel):
    status: VehicleStatus


class DriverStatusInput(APIModel):
    status: DriverStatus


class AssignmentInput(APIModel):
    driver_id: str | None


class DeviceInfo(APIModel):
    receiver_id: str
    receiver_state: Literal["ok", "error", "not_reporting"]
    receiver_updated_at: datetime | None
    phone_model: str | None
    phone_sync_at: datetime | None
    last_recording_at: datetime | None
    last_upload_state: Literal["uploaded", "uploading", "queued", "failed"] | None


class Location(APIModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    at: datetime


class JourneyRef(APIModel):
    id: str
    vehicle_id: str
    driver_id: str
    route: str
    status: Literal["scheduled", "active", "delayed", "completed", "cancelled"]
    planned_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    driver_name: str | None
    vehicle_registration: str | None


class VehicleView(APIModel):
    id: str
    registration: str
    type: Literal["truck", "van", "pickup", "reefer"]
    model: str
    status: VehicleStatus
    driver_id: str | None
    device: DeviceInfo | None
    last_location: Location | None
    driver_name: str | None
    current_journey: JourneyRef | None


class MobileAccount(APIModel):
    email: str | None
    active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: datetime | None


class DriverView(APIModel):
    id: str
    name: str
    phone: str | None
    email: str | None
    status: DriverStatus
    mobile_account: MobileAccount | None
    vehicle_id: str | None
    vehicle_registration: str | None
    current_journey: JourneyRef | None
    availability: Literal["available", "on_journey", "deactivated"]


class AssignableDriver(APIModel):
    id: str
    name: str


class IssuedCredentials(APIModel):
    driver: DriverView
    email: str
    temporary_password: str


class DriverRecord(APIModel):
    id: str
    title: str
    severity: Severity
    status: Literal["open", "acknowledged", "investigating", "closed"]
    journey_id: str
    at: datetime


class VehicleDetail(APIModel):
    vehicle: VehicleView
    history: list[JourneyRef]


class DriverDetail(APIModel):
    driver: DriverView
    history: list[JourneyRef]
    alerts: list[DriverRecord]
    incidents: list[DriverRecord]
