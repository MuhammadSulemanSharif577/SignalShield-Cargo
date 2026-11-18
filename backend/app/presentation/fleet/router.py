from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.application.authentication.use_cases.access_service import Principal
from app.application.fleet.schemas import (
    AssignableDriver, AssignmentInput, DriverDetail, DriverInput,
    DriverStatusInput, DriverView, IssuedCredentials, VehicleDetail, VehicleInput,
    VehicleStatusInput, VehicleView,
)
from app.application.fleet.use_cases.fleet_service import FleetService
from app.core.errors import APIError
from app.infrastructure.database.connection import get_db
from app.infrastructure.repositories.fleet_repository_implementation import SQLAlchemyFleetRepository
from app.presentation.authentication.dependencies import require_permissions

router = APIRouter(tags=["Fleet"])


def get_fleet_service(db: Session = Depends(get_db)) -> FleetService:
    return FleetService(SQLAlchemyFleetRepository(db))


@router.get("/vehicles", response_model=list[VehicleView])
def list_vehicles(principal: Principal = Depends(require_permissions("vehicles:view")),
                  service: FleetService = Depends(get_fleet_service)):
    return service.list_vehicles(principal)


@router.post("/vehicles", response_model=VehicleView, status_code=201)
def create_vehicle(request: VehicleInput, principal: Principal = Depends(require_permissions("vehicles:manage")),
                   service: FleetService = Depends(get_fleet_service)):
    return service.create_vehicle(request, principal)


@router.get("/vehicles/{vehicle_id}", response_model=VehicleDetail)
def get_vehicle(vehicle_id: str, principal: Principal = Depends(require_permissions("vehicles:view")),
                service: FleetService = Depends(get_fleet_service)):
    return service.get_vehicle(vehicle_id, principal)


@router.put("/vehicles/{vehicle_id}", response_model=VehicleView)
def update_vehicle(vehicle_id: str, request: VehicleInput,
                   principal: Principal = Depends(require_permissions("vehicles:manage")),
                   service: FleetService = Depends(get_fleet_service)):
    return service.update_vehicle(vehicle_id, request, principal)


@router.post("/vehicles/{vehicle_id}/status", response_model=VehicleView)
def set_vehicle_status(vehicle_id: str, request: VehicleStatusInput,
                       principal: Principal = Depends(require_permissions("vehicles:manage")),
                       service: FleetService = Depends(get_fleet_service)):
    return service.set_vehicle_status(vehicle_id, request.status, principal)


@router.put("/vehicles/{vehicle_id}/driver", response_model=VehicleView)
def assign_driver(vehicle_id: str, request: AssignmentInput,
                  principal: Principal = Depends(require_permissions("vehicles:manage")),
                  service: FleetService = Depends(get_fleet_service)):
    return service.assign_driver(vehicle_id, request.driver_id, principal)


# This static path must be registered before /drivers/{driver_id}.
@router.get("/drivers/assignable", response_model=list[AssignableDriver])
def assignable_drivers(principal: Principal = Depends(require_permissions("drivers:view")),
                       service: FleetService = Depends(get_fleet_service)):
    return service.assignable_drivers()


@router.get("/drivers", response_model=list[DriverView])
def list_drivers(principal: Principal = Depends(require_permissions("drivers:view")),
                 service: FleetService = Depends(get_fleet_service)):
    return service.list_drivers(principal)


@router.post("/drivers", response_model=DriverView, status_code=201)
def create_driver(request: DriverInput, principal: Principal = Depends(require_permissions("drivers:manage")),
                  service: FleetService = Depends(get_fleet_service)):
    return service.create_driver(request, principal)


@router.get("/drivers/{driver_id}", response_model=DriverDetail)
def get_driver(driver_id: str, principal: Principal = Depends(require_permissions("drivers:view")),
               service: FleetService = Depends(get_fleet_service)):
    return service.get_driver(driver_id, principal)


@router.put("/drivers/{driver_id}", response_model=DriverView)
def update_driver(driver_id: str, request: DriverInput,
                  principal: Principal = Depends(require_permissions("drivers:manage")),
                  service: FleetService = Depends(get_fleet_service)):
    return service.update_driver(driver_id, request, principal)


@router.post("/drivers/{driver_id}/status", response_model=DriverView)
def set_driver_status(driver_id: str, request: DriverStatusInput,
                      principal: Principal = Depends(require_permissions("drivers:manage")),
                      service: FleetService = Depends(get_fleet_service)):
    return service.set_driver_status(driver_id, request.status, principal)


@router.post("/drivers/{driver_id}/credentials", response_model=IssuedCredentials, status_code=201)
async def create_credentials(driver_id: str, request: Request,
                             principal: Principal = Depends(require_permissions("drivers:credentials")),
                             service: FleetService = Depends(get_fleet_service)):
    if await request.body():
        raise APIError(422, "validation", "No request body is allowed; the login uses the driver's saved email.")
    return await run_in_threadpool(service.issue_credentials, driver_id, principal)


@router.post("/drivers/{driver_id}/credentials/reset-password", response_model=IssuedCredentials)
def reset_credentials(driver_id: str,
                      principal: Principal = Depends(require_permissions("drivers:credentials")),
                      service: FleetService = Depends(get_fleet_service)):
    return service.issue_credentials(driver_id, principal, reset=True)


@router.delete("/drivers/{driver_id}/credentials", status_code=204)
def revoke_credentials(driver_id: str,
                       principal: Principal = Depends(require_permissions("drivers:credentials")),
                       service: FleetService = Depends(get_fleet_service)):
    service.revoke_credentials(driver_id)
    return Response(status_code=204)
