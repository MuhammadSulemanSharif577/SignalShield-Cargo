from sqlalchemy import select

from app.core.time import aware
from app.infrastructure.database.models.dashboard_model import (
    ActivityModel, DeviceIssueModel, RecordingModel, ShipmentModel,
)
from app.infrastructure.database.models.fleet_model import DriverRecordModel
from app.infrastructure.repositories.fleet_repository_implementation import SQLAlchemyFleetRepository


class SQLAlchemyDashboardRepository(SQLAlchemyFleetRepository):
    def _rows(self, model, *fields) -> list[dict]:
        return [{key: aware(getattr(row, key)) if key.endswith("_at") or key in {"at", "since"}
                 else getattr(row, key) for key in fields} for row in self.db.scalars(select(model))]

    def shipments(self) -> list[dict]:
        return self._rows(ShipmentModel, "id", "status", "updated_at")

    def security_records(self) -> list[dict]:
        return self._rows(DriverRecordModel, "id", "kind", "title", "severity", "status", "journey_id", "at", "updated_at")

    def recordings(self) -> list[dict]:
        return self._rows(RecordingModel, "id", "recorded_at", "upload_state", "processing_state", "updated_at")

    def device_issues(self) -> list[dict]:
        return self._rows(DeviceIssueModel, "id", "vehicle_id", "kind", "device", "detail", "since", "resolved_at", "updated_at")

    def activity(self) -> list[dict]:
        return self._rows(ActivityModel, "id", "at", "actor", "text", "kind")
