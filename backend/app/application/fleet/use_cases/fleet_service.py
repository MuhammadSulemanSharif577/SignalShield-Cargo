import re
import secrets
from uuid import uuid4

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.application.authentication.use_cases.access_service import Principal
from app.application.fleet.schemas import (
    AssignableDriver,
    DeviceInfo,
    DriverDetail,
    DriverInput,
    DriverRecord,
    DriverView,
    IssuedCredentials,
    JourneyRef,
    VehicleDetail,
    VehicleInput,
    VehicleView,
)
from app.core.errors import APIError
from app.core.security import hash_password
from app.domain.fleet.entities import Driver, Journey, Vehicle
from app.domain.fleet.repository import FleetRepository

EMAIL = TypeAdapter(EmailStr)


def current_journey(journeys: list[Journey]) -> Journey | None:
    return next(
        (journey for journey in journeys if journey.status in {"active", "delayed"}),
        None,
    )


class FleetService:
    def __init__(self, repository: FleetRepository):
        self.repository = repository

    def _vehicle(self, vehicle_id: str, lock: bool = False) -> Vehicle:
        vehicle = self.repository.get_vehicle(vehicle_id, lock)
        if vehicle is None:
            raise APIError(404, "not_found", "Vehicle not found.")
        return vehicle

    def _driver(self, driver_id: str, lock: bool = False) -> Driver:
        driver = self.repository.get_driver(driver_id, lock)
        if driver is None:
            raise APIError(404, "not_found", "Driver not found.")
        return driver

    def vehicle_view(self, vehicle: Vehicle, principal: Principal) -> VehicleView:
        driver = (
            self.repository.get_driver(vehicle.driver_id) if vehicle.driver_id else None
        )
        journey = current_journey(self.repository.journeys(vehicle_id=vehicle.id))
        return VehicleView(
            id=vehicle.id,
            registration=vehicle.registration,
            type=vehicle.type,
            model=vehicle.model,
            status=vehicle.status,
            driver_id=vehicle.driver_id,
            device=(
                DeviceInfo.model_validate(vehicle.device) if vehicle.device else None
            ),
            last_location=(
                vehicle.last_location if principal.can("tracking:view") else None
            ),
            driver_name=driver.name if driver else None,
            current_journey=(
                JourneyRef.model_validate(journey)
                if journey and principal.can("journeys:view", "journeys:manage")
                else None
            ),
        )

    def driver_view(self, driver: Driver, principal: Principal) -> DriverView:
        vehicle = (
            self.repository.get_vehicle(driver.vehicle_id)
            if driver.vehicle_id
            else None
        )
        journey = current_journey(self.repository.journeys(driver_id=driver.id))
        contacts = principal.can("drivers:manage")
        return DriverView(
            id=driver.id,
            name=driver.name,
            phone=driver.phone if contacts else None,
            email=driver.email if principal.can("drivers:manage", "drivers:credentials") else None,
            status=driver.status,
            user_account=(
                driver.user_account if principal.can("drivers:credentials") else None
            ),
            vehicle_id=driver.vehicle_id,
            vehicle_registration=vehicle.registration if vehicle else None,
            current_journey=(
                JourneyRef.model_validate(journey)
                if journey and principal.can("journeys:view", "journeys:manage")
                else None
            ),
            availability=(
                "deactivated"
                if driver.status != "active"
                else "on_journey" if journey else "available"
            ),
        )

    def list_vehicles(self, principal: Principal) -> list[VehicleView]:
        return [
            self.vehicle_view(vehicle, principal)
            for vehicle in self.repository.list_vehicles()
        ]

    def get_vehicle(self, vehicle_id: str, principal: Principal) -> VehicleDetail:
        vehicle = self._vehicle(vehicle_id)
        history = (
            self.repository.journeys(vehicle_id=vehicle.id)
            if principal.can("journeys:view", "journeys:manage")
            else []
        )
        return VehicleDetail(
            vehicle=self.vehicle_view(vehicle, principal),
            history=[JourneyRef.model_validate(journey) for journey in history],
        )

    def _device(self, receiver_id: str) -> dict | None:
        if not receiver_id:
            return None
        return {
            "receiver_id": receiver_id,
            "receiver_state": "not_reporting",
            "receiver_updated_at": None,
            "phone_model": None,
            "phone_sync_at": None,
            "last_recording_at": None,
            "last_upload_state": None,
        }

    def create_vehicle(
        self, request: VehicleInput, principal: Principal
    ) -> VehicleView:
        vehicle = Vehicle(
            str(uuid4()),
            request.registration,
            request.type,
            request.model,
            request.status,
            receiver_id=request.receiver_id or None,
            device=self._device(request.receiver_id),
        )
        vehicle = self.repository.save_vehicle(vehicle)
        self.repository.commit()
        return self.vehicle_view(vehicle, principal)

    def _check_vehicle_status(self, vehicle: Vehicle, status: str):
        if status != "active" and current_journey(
            self.repository.journeys(vehicle_id=vehicle.id)
        ):
            raise APIError(
                409, "rule", "A vehicle on a current journey must remain active."
            )

    def update_vehicle(
        self, vehicle_id: str, request: VehicleInput, principal: Principal
    ) -> VehicleView:
        vehicle = self._vehicle(vehicle_id, lock=True)
        self._check_vehicle_status(vehicle, request.status)
        receiver_id = request.receiver_id or None
        if receiver_id != vehicle.receiver_id:
            if current_journey(self.repository.journeys(vehicle_id=vehicle.id)):
                raise APIError(
                    409,
                    "rule",
                    "A receiver cannot be replaced during a current journey.",
                )
            vehicle.receiver_id, vehicle.device = receiver_id, self._device(
                request.receiver_id
            )
        vehicle.registration, vehicle.type, vehicle.model, vehicle.status = (
            request.registration,
            request.type,
            request.model,
            request.status,
        )
        vehicle = self.repository.save_vehicle(vehicle)
        self.repository.commit()
        return self.vehicle_view(vehicle, principal)

    def set_vehicle_status(
        self, vehicle_id: str, status: str, principal: Principal
    ) -> VehicleView:
        vehicle = self._vehicle(vehicle_id, lock=True)
        self._check_vehicle_status(vehicle, status)
        vehicle.status = status
        vehicle = self.repository.save_vehicle(vehicle)
        self.repository.commit()
        return self.vehicle_view(vehicle, principal)

    def assign_driver(
        self, vehicle_id: str, driver_id: str | None, principal: Principal
    ) -> VehicleView:
        vehicle = self._vehicle(vehicle_id, lock=True)
        if driver_id == vehicle.driver_id:
            return self.vehicle_view(vehicle, principal)
        if current_journey(self.repository.journeys(vehicle_id=vehicle.id)):
            raise APIError(
                409, "rule", "The driver cannot be changed during a current journey."
            )
        if driver_id is not None:
            driver = self._driver(driver_id, lock=True)
            if vehicle.status != "active" or driver.status != "active":
                raise APIError(
                    409, "rule", "Only active vehicles and drivers can be assigned."
                )
            if driver.vehicle_id is not None:
                raise APIError(
                    409, "rule", "This driver is already assigned to a vehicle."
                )
            if current_journey(self.repository.journeys(driver_id=driver.id)):
                raise APIError(
                    409, "rule", "This driver is already on a current journey."
                )
        vehicle.driver_id = driver_id
        vehicle = self.repository.save_vehicle(vehicle)
        self.repository.commit()
        return self.vehicle_view(vehicle, principal)

    def assignable_drivers(self) -> list[AssignableDriver]:
        return [
            AssignableDriver(id=driver.id, name=driver.name)
            for driver in self.repository.list_drivers()
            if driver.status == "active"
            and driver.vehicle_id is None
            and current_journey(self.repository.journeys(driver_id=driver.id)) is None
        ]

    def list_drivers(self, principal: Principal) -> list[DriverView]:
        return [
            self.driver_view(driver, principal)
            for driver in self.repository.list_drivers()
        ]

    def get_driver(self, driver_id: str, principal: Principal) -> DriverDetail:
        driver = self._driver(driver_id)
        history = (
            self.repository.journeys(driver_id=driver.id)
            if principal.can("journeys:view", "journeys:manage")
            else []
        )
        alerts = (
            self.repository.records(driver.id, "alert")
            if principal.can("alerts:view", "alerts:manage")
            else []
        )
        incidents = (
            self.repository.records(driver.id, "incident")
            if principal.can("incidents:view", "incidents:manage")
            else []
        )
        return DriverDetail(
            driver=self.driver_view(driver, principal),
            history=[JourneyRef.model_validate(journey) for journey in history],
            alerts=[DriverRecord.model_validate(record) for record in alerts],
            incidents=[DriverRecord.model_validate(record) for record in incidents],
        )

    def _apply_driver_input(self, driver: Driver, request: DriverInput):
        driver.name = request.name
        driver.phone = re.sub(r"[\s-]", "", request.phone)
        driver.email = str(request.email)

    def create_driver(self, request: DriverInput, principal: Principal) -> DriverView:
        driver = Driver(str(uuid4()), request.name, request.phone, str(request.email))
        self._apply_driver_input(driver, request)
        driver = self.repository.save_driver(driver)
        self.repository.commit()
        return self.driver_view(driver, principal)

    def update_driver(
        self, driver_id: str, request: DriverInput, principal: Principal
    ) -> DriverView:
        driver = self._driver(driver_id, lock=True)
        self._apply_driver_input(driver, request)
        driver = self.repository.save_driver(driver)
        self.repository.commit()
        return self.driver_view(driver, principal)

    def set_driver_status(
        self, driver_id: str, status: str, principal: Principal
    ) -> DriverView:
        driver = self._driver(driver_id, lock=True)
        if status != "active" and current_journey(
            self.repository.journeys(driver_id=driver.id)
        ):
            raise APIError(
                409, "rule", "A driver on a current journey cannot be deactivated."
            )
        if status != "active" and driver.vehicle_id:
            raise APIError(
                409,
                "rule",
                "Unassign the driver's vehicle before deactivating the driver.",
            )
        driver.status = status
        driver = self.repository.save_driver(driver)
        self.repository.commit()
        return self.driver_view(driver, principal)

    def issue_credentials(
        self, driver_id: str, principal: Principal, *, reset: bool = False
    ) -> IssuedCredentials:
        driver = self._driver(driver_id, lock=True)
        if driver.status != "active":
            raise APIError(
                409, "rule", "Credentials can only be issued to active drivers."
            )
        if not reset and driver.user_account is not None:
            raise APIError(409, "conflict", "This driver already has a linked user account. Reset its password to restore access.")
        if reset and driver.user_account is None:
            raise APIError(404, "not_found", "This driver has no linked user account.")
        try:
            email = EMAIL.validate_python(driver.email).lower()
        except ValidationError:
            raise APIError(422, "validation", "Save a valid driver email before issuing credentials.") from None
        password = "Aa1!" + secrets.token_urlsafe(18)
        self.repository.set_credentials(driver.id, hash_password(password))
        self.repository.commit()
        return IssuedCredentials(
            driver=self.driver_view(self._driver(driver_id), principal),
            email=str(email),
            temporary_password=password,
        )

    def revoke_credentials(self, driver_id: str):
        self._driver(driver_id, lock=True)
        self.repository.revoke_credentials(driver_id)
        self.repository.commit()
