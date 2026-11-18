"""Register all persistence models with the shared SQLAlchemy metadata."""

from app.infrastructure.database.models.user_model import UserModel
from app.infrastructure.database.models.access_model import (
    RoleModel, SessionModel, user_roles,
)
from app.infrastructure.database.models.fleet_model import (
    DriverModel, DriverRecordModel, JourneyModel, VehicleModel,
)
from app.infrastructure.database.models.dashboard_model import (
    ActivityModel, DeviceIssueModel, RecordingModel, ShipmentModel,
)

__all__ = [
    "UserModel", "RoleModel", "SessionModel", "user_roles",
    "DriverModel", "DriverRecordModel", "JourneyModel", "VehicleModel",
    "ActivityModel", "DeviceIssueModel", "RecordingModel", "ShipmentModel",
]
