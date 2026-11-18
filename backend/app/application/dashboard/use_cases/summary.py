from datetime import datetime, timedelta

from app.application.authentication.use_cases.access_service import Principal
from app.application.dashboard.schemas import (
    ActiveJourney, ActivityItem, DashboardSnapshot, DeviceIssue, IncidentItem,
)
from app.core.time import aware, utcnow
from app.domain.dashboard.repository import DashboardRepository


def latest(values):
    return max((value for value in values if value is not None), default=None)


def device_time(value):
    return aware(datetime.fromisoformat(value)) if isinstance(value, str) else aware(value)


class DashboardSummary:
    def __init__(self, repository: DashboardRepository):
        self.repository = repository

    def execute(self, principal: Principal) -> DashboardSnapshot:
        now = utcnow()
        snapshot = DashboardSnapshot(generated_at=now)
        vehicles = self.repository.list_vehicles()
        drivers = self.repository.list_drivers()
        journeys = self.repository.journeys()
        live = [journey for journey in journeys if journey.status in {"active", "delayed"}]
        fleet_times = []
        if principal.can("vehicles:view"):
            snapshot.fleet.vehicles = len(vehicles)
            snapshot.fleet.vehicles_unavailable = sum(vehicle.status != "active" for vehicle in vehicles)
            snapshot.fleet.vehicles_on_journey = len({journey.vehicle_id for journey in live}) if principal.can("journeys:view") else 0
            fleet_times.extend(vehicle.updated_at for vehicle in vehicles)
        if principal.can("drivers:view"):
            snapshot.fleet.drivers = len(drivers)
            snapshot.fleet.drivers_on_journey = len({journey.driver_id for journey in live}) if principal.can("journeys:view") else 0
            fleet_times.extend(driver.updated_at for driver in drivers)
        if fleet_times and principal.can("journeys:view"):
            fleet_times.extend(journey.updated_at for journey in journeys)
        snapshot.fleet.updated_at = latest(fleet_times)

        journey_times = []
        if principal.can("journeys:view"):
            for status in ("active", "scheduled", "completed", "delayed"):
                setattr(snapshot.journeys, status, sum(journey.status == status for journey in journeys))
            journey_times.extend(journey.updated_at for journey in journeys)
            vehicle_map = {vehicle.id: vehicle for vehicle in vehicles}
            for journey in live:
                vehicle = vehicle_map.get(journey.vehicle_id)
                location = vehicle.last_location if vehicle else None
                snapshot.active_journeys.append(ActiveJourney(
                    id=journey.id, vehicle=(journey.vehicle_registration or "") if principal.can("vehicles:view") else "",
                    driver=(journey.driver_name or "") if principal.can("drivers:view") else "",
                    route=journey.route, progress=journey.progress,
                    last_location_at=location.get("at") if location and principal.can("tracking:view") else None,
                    integrity=journey.integrity if principal.can("analysis:view", "alerts:view") else "not_assessed",
                ))
        if principal.can("shipments:view"):
            shipments = self.repository.shipments()
            snapshot.journeys.shipments_in_transit = sum(row["status"] == "in_transit" for row in shipments)
            journey_times.extend(row["updated_at"] for row in shipments)
        snapshot.journeys.updated_at = latest(journey_times)

        records = self.repository.security_records()
        if principal.can("alerts:view"):
            alerts = [row for row in records if row["kind"] == "alert"]
            for row in alerts:
                statuses = snapshot.alerts.matrix.get(row["severity"], {})
                if row["status"] in statuses:
                    statuses[row["status"]] += 1
            snapshot.alerts.updated_at = latest(row["updated_at"] for row in alerts)
        if principal.can("incidents:view"):
            snapshot.incidents = [IncidentItem(
                id=row["id"], title=row["title"], severity=row["severity"], status=row["status"],
                journey_id=row["journey_id"], opened_at=row["at"],
            ) for row in sorted(records, key=lambda row: row["at"], reverse=True)
                if row["kind"] == "incident" and row["status"] in {"open", "investigating", "awaiting_review"}][:20]

        device_times = [device_time(vehicle.device.get("receiver_updated_at") or vehicle.device.get("receiverUpdatedAt"))
                        for vehicle in vehicles if vehicle.device]
        if principal.can("gnss:view"):
            recordings = self.repository.recordings()
            snapshot.gnss.receivers_expected = sum(bool(vehicle.receiver_id) for vehicle in vehicles)
            for vehicle in vehicles:
                device = vehicle.device or {}
                state = device.get("receiver_state", device.get("receiverState"))
                at = device_time(device.get("receiver_updated_at", device.get("receiverUpdatedAt")))
                if state == "ok" and at and now - timedelta(minutes=5) <= at <= now:
                    snapshot.gnss.receivers_reporting += 1
            snapshot.gnss.recordings_today = sum(row["recorded_at"].date() == now.date() for row in recordings)
            for state in ("uploading", "queued", "failed"):
                setattr(snapshot.gnss, state, sum(row["upload_state"] == state for row in recordings))
            snapshot.gnss.processing = sum(row["processing_state"] == "processing" for row in recordings)
            snapshot.gnss.updated_at = latest(device_times + [row["updated_at"] for row in recordings])
        if principal.can("gnss:view", "vehicles:view"):
            issues = self.repository.device_issues()
            registrations = {vehicle.id: vehicle.registration for vehicle in vehicles}
            snapshot.devices = [DeviceIssue(
                id=row["id"], kind=row["kind"], device=row["device"],
                vehicle=registrations.get(row["vehicle_id"], ""), detail=row["detail"], since=row["since"],
            ) for row in issues if row["resolved_at"] is None]
            snapshot.devices_updated_at = latest(device_times + [row["updated_at"] for row in issues])

        kind_permissions = {"journey": ("journeys:view",), "alert": ("alerts:view",),
                            "upload": ("gnss:view",), "user": ("users:view", "users:manage"),
                            "incident": ("incidents:view",)}
        snapshot.activity = [ActivityItem.model_validate(row)
                             for row in sorted(self.repository.activity(), key=lambda row: row["at"], reverse=True)
                             if principal.can(*kind_permissions.get(row["kind"], ()))][:30]
        return snapshot
