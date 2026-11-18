from datetime import datetime
from typing import Literal

from pydantic import Field

from app.application.fleet.schemas import Severity
from app.application.schemas import APIModel


class Timed(APIModel):
    updated_at: datetime | None = None


class FleetSummary(Timed):
    vehicles: int = 0
    vehicles_on_journey: int = 0
    vehicles_unavailable: int = 0
    drivers: int = 0
    drivers_on_journey: int = 0


class JourneySummary(Timed):
    active: int = 0
    scheduled: int = 0
    completed: int = 0
    delayed: int = 0
    shipments_in_transit: int = 0


class AlertSummary(Timed):
    matrix: dict[Severity, dict[Literal["open", "acknowledged", "investigating"], int]] = Field(
        default_factory=lambda: {severity: {status: 0 for status in ("open", "acknowledged", "investigating")}
                                 for severity in ("critical", "high", "medium", "low")}
    )


class GnssSummary(Timed):
    receivers_expected: int = 0
    receivers_reporting: int = 0
    recordings_today: int = 0
    uploading: int = 0
    queued: int = 0
    failed: int = 0
    processing: int = 0


class DeviceIssue(APIModel):
    id: str
    kind: Literal["receiver_error", "phone_offline", "sync_delayed"]
    device: str
    vehicle: str
    detail: str
    since: datetime


class ActiveJourney(APIModel):
    id: str
    vehicle: str
    driver: str
    route: str
    progress: float
    last_location_at: datetime | None
    integrity: Literal["no_findings", "under_review", "alert_open", "not_assessed"]


class IncidentItem(APIModel):
    id: str
    title: str
    severity: Severity
    status: Literal["open", "investigating", "awaiting_review"]
    journey_id: str
    opened_at: datetime


class ActivityItem(APIModel):
    id: str
    at: datetime
    actor: str
    text: str
    kind: Literal["journey", "alert", "upload", "user", "incident"]


class DashboardSnapshot(APIModel):
    generated_at: datetime
    fleet: FleetSummary = Field(default_factory=FleetSummary)
    journeys: JourneySummary = Field(default_factory=JourneySummary)
    alerts: AlertSummary = Field(default_factory=AlertSummary)
    gnss: GnssSummary = Field(default_factory=GnssSummary)
    devices: list[DeviceIssue] = Field(default_factory=list)
    devices_updated_at: datetime | None = None
    active_journeys: list[ActiveJourney] = Field(default_factory=list)
    incidents: list[IncidentItem] = Field(default_factory=list)
    activity: list[ActivityItem] = Field(default_factory=list)
