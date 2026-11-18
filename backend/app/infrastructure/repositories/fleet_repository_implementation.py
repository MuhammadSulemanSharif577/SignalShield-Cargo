from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.time import aware, utcnow
from app.core.errors import APIError
from app.domain.authentication.permissions import DRIVER_ROLE_ID
from app.domain.fleet.entities import Driver, Journey, Vehicle
from app.infrastructure.database.models.fleet_model import (
    DriverModel, DriverRecordModel, JourneyModel, VehicleModel,
)
from app.infrastructure.database.models.user_model import UserModel
from app.infrastructure.database.models.access_model import SessionModel, user_roles


class SQLAlchemyFleetRepository:
    def __init__(self, db: Session):
        self.db = db

    def commit(self):
        self.db.commit()

    def _vehicle(self, model: VehicleModel) -> Vehicle:
        return Vehicle(model.id, model.registration, model.type, model.model, model.status,
                       model.driver_id, model.receiver_id, model.device, model.last_location,
                       aware(model.updated_at))

    def list_vehicles(self) -> list[Vehicle]:
        return [self._vehicle(row) for row in self.db.scalars(select(VehicleModel).order_by(VehicleModel.registration))]

    def get_vehicle(self, vehicle_id: str, lock: bool = False) -> Vehicle | None:
        query = select(VehicleModel).where(VehicleModel.id == vehicle_id)
        model = self.db.scalar(query.with_for_update() if lock else query)
        return self._vehicle(model) if model else None

    def save_vehicle(self, vehicle: Vehicle) -> Vehicle:
        model = self.db.get(VehicleModel, vehicle.id) or VehicleModel(id=vehicle.id)
        for key in ("registration", "type", "model", "status", "driver_id", "receiver_id", "device", "last_location"):
            setattr(model, key, getattr(vehicle, key))
        model.updated_at = utcnow()
        self.db.add(model)
        self.db.flush()
        return self._vehicle(model)

    def _driver(self, model: DriverModel) -> Driver:
        account = self.db.get(UserModel, model.user_id) if model.user_id else None
        user_account = None if account is None else {
            "id": str(account.id), "email": account.email, "status": account.status,
            "must_change_password": account.must_change_password,
            "created_at": aware(account.created_at), "last_login": aware(account.last_login),
        }
        vehicle_id = self.db.scalar(select(VehicleModel.id).where(VehicleModel.driver_id == model.id))
        return Driver(model.id, model.name, model.phone, model.email, model.status,
                       user_account, vehicle_id, aware(model.updated_at))

    def list_drivers(self) -> list[Driver]:
        return [self._driver(row) for row in self.db.scalars(select(DriverModel).order_by(DriverModel.name))]

    def get_driver(self, driver_id: str, lock: bool = False) -> Driver | None:
        query = select(DriverModel).where(DriverModel.id == driver_id)
        model = self.db.scalar(query.with_for_update() if lock else query)
        return self._driver(model) if model else None

    def save_driver(self, driver: Driver) -> Driver:
        model = self.db.get(DriverModel, driver.id) or DriverModel(id=driver.id)
        for key in ("name", "phone", "email", "status"):
            setattr(model, key, getattr(driver, key))
        model.updated_at = utcnow()
        self.db.add(model)
        # Fleet changes lock the driver first, then its login identity.
        account = self.db.scalar(select(UserModel).where(UserModel.id == model.user_id).with_for_update()) if model.user_id else None
        if account:
            if account.email != driver.email:
                self._revoke_sessions(account.id)
            account.full_name, account.email = driver.name, driver.email
            if driver.status != "active":
                account.status, account.is_active = "inactive", False
                self._revoke_sessions(account.id)
        self.db.flush()
        return self._driver(model)

    def journeys(self, vehicle_id: str | None = None, driver_id: str | None = None) -> list[Journey]:
        query = select(JourneyModel).order_by(JourneyModel.planned_at.desc())
        if vehicle_id:
            query = query.where(JourneyModel.vehicle_id == vehicle_id)
        if driver_id:
            query = query.where(JourneyModel.driver_id == driver_id)
        result = []
        for row in self.db.scalars(query):
            driver = self.db.get(DriverModel, row.driver_id)
            vehicle = self.db.get(VehicleModel, row.vehicle_id)
            result.append(Journey(
                row.id, row.vehicle_id, row.driver_id, row.route, row.status,
                aware(row.planned_at), aware(row.started_at), aware(row.ended_at),
                driver.name if driver else None, vehicle.registration if vehicle else None,
                row.progress, row.integrity, aware(row.updated_at),
            ))
        return result

    def records(self, driver_id: str, kind: str) -> list[dict]:
        return [{"id": row.id, "title": row.title, "severity": row.severity,
                 "status": "investigating" if row.status == "awaiting_review" else row.status,
                 "journey_id": row.journey_id, "at": aware(row.at)}
                for row in self.db.scalars(select(DriverRecordModel).where(
                    DriverRecordModel.driver_id == driver_id, DriverRecordModel.kind == kind
                ).order_by(DriverRecordModel.at.desc()))]

    def set_credentials(self, driver_id: str, password_hash: str):
        driver = self.db.get(DriverModel, driver_id)
        if driver.user_id:
            account = self.db.scalar(select(UserModel).where(UserModel.id == driver.user_id).with_for_update())
        else:
            if self.db.scalar(select(UserModel.id).where(UserModel.email == driver.email)):
                raise APIError(409, "conflict", "This email already belongs to a user account. No accounts were linked or changed.")
            account = UserModel(full_name=driver.name, email=driver.email, hashed_password=password_hash,
                                status="active", is_active=True)
            self.db.add(account)
            self.db.flush()
            driver.user_id = account.id
            self.db.execute(user_roles.insert().values(user_id=account.id, role_id=DRIVER_ROLE_ID))
        account.hashed_password = password_hash
        account.status, account.is_active = "active", True
        account.must_change_password = True
        account.failed_logins, account.locked_until = 0, None
        self._revoke_sessions(account.id)
        self.db.flush()

    def _revoke_sessions(self, user_id: int):
        self.db.execute(delete(SessionModel).where(SessionModel.user_id == user_id))

    def revoke_credentials(self, driver_id: str):
        driver = self.db.get(DriverModel, driver_id)
        if driver.user_id:
            account = self.db.scalar(select(UserModel).where(UserModel.id == driver.user_id).with_for_update())
            account.status, account.is_active = "inactive", False
            self._revoke_sessions(account.id)
