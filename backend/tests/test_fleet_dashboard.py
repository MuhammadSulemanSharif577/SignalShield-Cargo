from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.core.security import verify_password
from app.core.time import utcnow
from app.infrastructure.database.models.dashboard_model import ActivityModel, DeviceIssueModel, RecordingModel, ShipmentModel
from app.infrastructure.database.models.fleet_model import DriverModel, DriverRecordModel, JourneyModel, MobileAccountModel, VehicleModel


@pytest.fixture
def fleet(client, admin):
    _, _, headers = admin
    driver_result = client.post("/api/v1/drivers", headers=headers, json={
        "name": "Driver One", "phone": "+1 234 567 890", "email": "driver@example.com",
    })
    assert driver_result.status_code == 201, driver_result.text
    vehicle_result = client.post("/api/v1/vehicles", headers=headers, json={
        "registration": "abc-123", "type": "truck", "model": "Cargo Truck",
        "status": "active", "receiverId": "RX-1",
    })
    assert vehicle_result.status_code == 201, vehicle_result.text
    return driver_result.json(), vehicle_result.json(), headers


def add_journey(db_factory, driver_id, vehicle_id, status="active"):
    with db_factory() as db:
        identifier = str(uuid4())
        db.add(JourneyModel(id=identifier, driver_id=driver_id, vehicle_id=vehicle_id,
            route="Warehouse to Port", status=status, planned_at=utcnow(),
            started_at=utcnow() if status == "active" else None, progress=42,
            integrity="alert_open", updated_at=utcnow()))
        db.commit()
        return identifier


def test_fleet_shapes_assignment_and_persistence(client, fleet):
    driver, vehicle, headers = fleet
    assert set(vehicle) == {"id", "registration", "type", "model", "status", "driverId", "device",
                            "lastLocation", "driverName", "currentJourney"}
    assert vehicle["registration"] == "ABC-123"
    assert vehicle["device"] == {
        "receiverId": "RX-1", "receiverState": "not_reporting", "receiverUpdatedAt": None,
        "phoneModel": None, "phoneSyncAt": None, "lastRecordingAt": None, "lastUploadState": None,
    }
    assert vehicle["lastLocation"] is None
    assert driver["phone"] == "+1234567890"
    assert driver["availability"] == "available"
    assert driver["mobileAccount"] is None
    assert client.get("/api/v1/drivers/assignable", headers=headers).json() == [{"id": driver["id"], "name": driver["name"]}]
    assigned = client.put(f"/api/v1/vehicles/{vehicle['id']}/driver", headers=headers, json={"driverId": driver["id"]})
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["driverName"] == driver["name"]
    assert client.get("/api/v1/drivers/assignable", headers=headers).json() == []
    detail = client.get(f"/api/v1/drivers/{driver['id']}", headers=headers).json()
    assert set(detail) == {"driver", "history", "alerts", "incidents"}
    assert detail["driver"]["vehicleId"] == vehicle["id"]
    assert detail["driver"]["vehicleRegistration"] == "ABC-123"
    assert detail["history"] == detail["alerts"] == detail["incidents"] == []
    assert client.post(f"/api/v1/drivers/{driver['id']}/status", headers=headers, json={"status": "inactive"}).status_code == 409
    assert client.put(f"/api/v1/vehicles/{vehicle['id']}/driver", headers=headers, json={"driverId": None}).status_code == 200
    assert client.post(f"/api/v1/drivers/{driver['id']}/status", headers=headers, json={"status": "inactive"}).json()["availability"] == "deactivated"
    assert client.put(f"/api/v1/vehicles/{vehicle['id']}/driver", headers=headers, json={"driverId": driver["id"]}).json()["code"] == "rule"
    assert client.get(f"/api/v1/vehicles/{vehicle['id']}", headers=headers).json()["history"] == []


def test_fleet_updates_and_uniqueness(client, fleet):
    driver, vehicle, headers = fleet
    body = {"registration": "ABC-123", "type": "van", "model": "New Van", "status": "active", "receiverId": "RX-2"}
    result = client.put(f"/api/v1/vehicles/{vehicle['id']}", headers=headers, json=body)
    assert result.status_code == 200, result.text
    assert result.json()["model"] == "New Van" and result.json()["device"]["receiverId"] == "RX-2"
    assert client.post("/api/v1/vehicles", headers=headers, json=body).status_code == 409
    assert client.post("/api/v1/vehicles", headers=headers, json={**body, "registration": "DEF-456"}).status_code == 409
    assert client.post("/api/v1/drivers", headers=headers, json={
        "name": "Other", "phone": "+1234567890", "email": "other@example.com",
    }).status_code == 409
    assert client.post("/api/v1/drivers", headers=headers, json={
        "name": "Other", "phone": "7654321", "email": "DRIVER@example.com",
    }).status_code == 409
    updated = client.put(f"/api/v1/drivers/{driver['id']}", headers=headers, json={
        "name": "Renamed Driver", "phone": "7654321", "email": " RENAMED@Example.com ",
    })
    assert updated.status_code == 200 and updated.json()["email"] == "renamed@example.com"
    assert client.get("/api/v1/drivers", headers=headers).json()[0]["name"] == "Renamed Driver"
    unavailable = client.post(f"/api/v1/vehicles/{vehicle['id']}/status", headers=headers, json={"status": "maintenance"})
    assert unavailable.status_code == 200
    assert client.put(f"/api/v1/vehicles/{vehicle['id']}/driver", headers=headers, json={"driverId": driver["id"]}).status_code == 409


def test_journey_constraints_and_history(client, fleet, db_factory):
    driver, vehicle, headers = fleet
    assert client.put(f"/api/v1/vehicles/{vehicle['id']}/driver", headers=headers, json={"driverId": driver["id"]}).status_code == 200
    journey_id = add_journey(db_factory, driver["id"], vehicle["id"])
    result = client.get(f"/api/v1/vehicles/{vehicle['id']}", headers=headers)
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["vehicle"]["currentJourney"]["id"] == journey_id
    assert payload["history"][0]["driverName"] == "Driver One"
    assert datetime.fromisoformat(payload["history"][0]["plannedAt"]).utcoffset() is not None
    for method, path, body in (
        ("POST", f"/vehicles/{vehicle['id']}/status", {"status": "inactive"}),
        ("POST", f"/drivers/{driver['id']}/status", {"status": "inactive"}),
        ("PUT", f"/vehicles/{vehicle['id']}/driver", {"driverId": None}),
        ("PUT", f"/vehicles/{vehicle['id']}", {"registration": "ABC-123", "type": "truck", "model": "Truck", "status": "active", "receiverId": "OTHER"}),
    ):
        response = client.request(method, "/api/v1" + path, json=body, headers=headers)
        assert response.status_code == 409 and response.json()["code"] == "rule"
    assert client.get(f"/api/v1/drivers/{driver['id']}", headers=headers).json()["driver"]["availability"] == "on_journey"


def test_credentials_only_reveal_temporary_password_on_issue(client, fleet, db_factory):
    driver, _, headers = fleet
    path = f"/api/v1/drivers/{driver['id']}/credentials"
    result = client.post(path, headers=headers)
    assert result.status_code == 201, result.text
    issued = result.json()
    assert set(issued) == {"driver", "email", "temporaryPassword"}
    assert issued["email"] == driver["email"]
    assert issued["driver"]["mobileAccount"]["email"] == driver["email"]
    assert "username" not in result.text
    assert issued["driver"]["mobileAccount"]["mustChangePassword"] is True
    with db_factory() as db:
        model = db.get(MobileAccountModel, driver["id"])
        assert verify_password(issued["temporaryPassword"], model.password_hash)
        assert model.password_hash != issued["temporaryPassword"]
        version = model.credential_version
    assert "temporaryPassword" not in client.get(f"/api/v1/drivers/{driver['id']}", headers=headers).text
    assert client.post(path, headers=headers).status_code == 409
    reset = client.post(path + "/reset-password", headers=headers)
    assert reset.status_code == 200, reset.text
    assert reset.json()["temporaryPassword"] != issued["temporaryPassword"]
    assert reset.json()["email"] == driver["email"]
    with db_factory() as db:
        assert db.get(MobileAccountModel, driver["id"]).credential_version == version + 1
    deleted = client.delete(path, headers=headers)
    assert deleted.status_code == 204 and deleted.content == b""
    assert client.get(f"/api/v1/drivers/{driver['id']}", headers=headers).json()["driver"]["email"] == driver["email"]
    assert client.post(path + "/reset-password", headers=headers).status_code == 404


@pytest.mark.parametrize("email", [None, "", " ", "invalid", "driver@"])
@pytest.mark.parametrize("method", ["POST", "PUT"])
def test_driver_email_is_required_and_valid(client, fleet, email, method):
    driver, _, headers = fleet
    path = "/api/v1/drivers" + (f"/{driver['id']}" if method == "PUT" else "")
    body = {"name": "Driver Two", "phone": "7654321", "email": email}
    for payload in (body, {key: value for key, value in body.items() if key != "email"}):
        response = client.request(method, path, headers=headers, json=payload)
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "validation"
    assert client.get(f"/api/v1/drivers/{driver['id']}", headers=headers).json()["driver"]["email"] == driver["email"]


def test_login_uses_saved_email_and_email_changes_preserve_password(client, fleet, db_factory):
    driver, _, headers = fleet
    path = f"/api/v1/drivers/{driver['id']}"
    for body in ({"username": "alternate"}, {"email": "alternate@example.com"}, {}):
        rejected = client.post(path + "/credentials", headers=headers, json=body)
        assert rejected.status_code == 422
        assert rejected.json()["code"] == "validation"
    issued = client.post(path + "/credentials", headers=headers).json()
    with db_factory() as db:
        original_hash = db.get(MobileAccountModel, driver["id"]).password_hash
    result = client.put(path, headers=headers, json={
        "name": driver["name"], "phone": driver["phone"], "email": " New.Login@Example.com ",
    })
    assert result.status_code == 200, result.text
    assert result.json()["email"] == result.json()["mobileAccount"]["email"] == "new.login@example.com"
    assert client.get(path, headers=headers).json()["driver"]["mobileAccount"]["email"] == "new.login@example.com"
    assert client.get("/api/v1/drivers", headers=headers).json()[0]["mobileAccount"]["email"] == "new.login@example.com"
    with db_factory() as db:
        assert db.get(MobileAccountModel, driver["id"]).password_hash == original_hash
        assert verify_password(issued["temporaryPassword"], original_hash)
        assert db.query(DriverModel).filter_by(email=driver["email"]).first() is None
        assert db.query(DriverModel).filter_by(email="new.login@example.com").one().id == driver["id"]
    reset = client.post(path + "/credentials/reset-password", headers=headers)
    assert reset.status_code == 200
    assert reset.json()["email"] == "new.login@example.com"


def test_driver_email_conflict_rolls_back_record_and_login(client, fleet, db_factory):
    driver, _, headers = fleet
    path = f"/api/v1/drivers/{driver['id']}"
    issued = client.post(path + "/credentials", headers=headers).json()
    other = client.post("/api/v1/drivers", headers=headers, json={
        "name": "Other Driver", "phone": "7654321", "email": "other@example.com",
    })
    assert other.status_code == 201
    response = client.put(path, headers=headers, json={
        "name": "Should not persist", "phone": driver["phone"], "email": " OTHER@EXAMPLE.COM ",
    })
    assert response.status_code == 409 and response.json()["code"] == "conflict"
    persisted = client.get(path, headers=headers).json()["driver"]
    assert persisted["name"] == driver["name"]
    assert persisted["email"] == persisted["mobileAccount"]["email"] == driver["email"]
    with db_factory() as db:
        assert verify_password(issued["temporaryPassword"], db.get(MobileAccountModel, driver["id"]).password_hash)


def test_inactive_driver_cannot_create_or_reset_login(client, fleet):
    driver, _, headers = fleet
    path = f"/api/v1/drivers/{driver['id']}"
    assert client.post(path + "/status", headers=headers, json={"status": "inactive"}).status_code == 200
    for suffix in ("/credentials", "/credentials/reset-password"):
        response = client.post(path + suffix, headers=headers)
        assert response.status_code == 409 and response.json()["code"] == "rule"


def test_invalid_persisted_email_cannot_issue_credentials(client, fleet, db_factory):
    driver, _, headers = fleet
    path = f"/api/v1/drivers/{driver['id']}/credentials"
    with db_factory() as db:
        db.get(DriverModel, driver["id"]).email = "invalid"
        db.commit()
    response = client.post(path, headers=headers)
    assert response.status_code == 422 and response.json()["code"] == "validation"
    with db_factory() as db:
        assert db.get(MobileAccountModel, driver["id"]) is None


def test_credential_permission_can_read_login_email_but_not_phone(client, fleet, make_user, login_headers):
    driver, _, admin_headers = fleet
    path = f"/api/v1/drivers/{driver['id']}"
    user, _ = make_user(["drivers:view", "drivers:credentials"])
    headers = login_headers(user)
    detail = client.get(path, headers=headers).json()["driver"]
    assert detail["email"] == driver["email"] and detail["phone"] is None
    issued = client.post(path + "/credentials", headers=headers)
    assert issued.status_code == 201, issued.text
    assert issued.json()["email"] == issued.json()["driver"]["mobileAccount"]["email"] == driver["email"]
    user, _ = make_user(["drivers:view"])
    restricted = login_headers(user)
    for record in (
        client.get(path, headers=restricted).json()["driver"],
        client.get("/api/v1/drivers", headers=restricted).json()[0],
    ):
        assert record["email"] is None and record["mobileAccount"] is None
    assert client.delete(path + "/credentials", headers=admin_headers).status_code == 204


def test_fleet_view_permissions_and_redaction(client, fleet, make_user, login_headers, db_factory):
    driver, vehicle, _ = fleet
    add_journey(db_factory, driver["id"], vehicle["id"])
    with db_factory() as db:
        model = db.get(VehicleModel, vehicle["id"])
        model.last_location = {"lat": 1.2, "lng": 3.4, "at": utcnow().isoformat()}
        db.commit()
    user, _ = make_user(["vehicles:view", "drivers:view"])
    headers = login_headers(user)
    details = client.get(f"/api/v1/drivers/{driver['id']}", headers=headers).json()
    assert details["driver"]["phone"] is None and details["driver"]["email"] is None
    assert details["driver"]["mobileAccount"] is None
    assert details["driver"]["currentJourney"] is None and details["history"] == []
    details = client.get(f"/api/v1/vehicles/{vehicle['id']}", headers=headers).json()
    assert details["vehicle"]["lastLocation"] is None and details["history"] == []
    assert client.post(f"/api/v1/vehicles/{vehicle['id']}/status", headers=headers, json={"status": "active"}).status_code == 403
    assert client.post(f"/api/v1/drivers/{driver['id']}/credentials", headers=headers, json={"username": "denied"}).status_code == 403


def test_empty_dashboard_is_complete_and_never_fabricates_freshness(client, admin):
    _, _, headers = admin
    result = client.get("/api/v1/dashboard/summary", headers=headers)
    assert result.status_code == 200, result.text
    data = result.json()
    assert set(data) == {"generatedAt", "fleet", "journeys", "alerts", "gnss", "devices", "devicesUpdatedAt", "activeJourneys", "incidents", "activity"}
    assert datetime.fromisoformat(data["generatedAt"]).utcoffset() is not None
    for name in ("fleet", "journeys", "gnss"):
        assert data[name]["updatedAt"] is None
        assert all(value == 0 for key, value in data[name].items() if key != "updatedAt")
    assert data["alerts"]["updatedAt"] is None
    assert set(data["alerts"]["matrix"]) == {"critical", "high", "medium", "low"}
    for statuses in data["alerts"]["matrix"].values():
        assert statuses == {"open": 0, "acknowledged": 0, "investigating": 0}
    assert data["devices"] == data["activeJourneys"] == data["incidents"] == data["activity"] == []
    assert data["devicesUpdatedAt"] is None


@pytest.fixture
def populated_dashboard(fleet, db_factory):
    driver, vehicle, headers = fleet
    journey_id = add_journey(db_factory, driver["id"], vehicle["id"])
    now = utcnow()
    with db_factory() as db:
        model = db.get(VehicleModel, vehicle["id"])
        model.device = {**model.device, "receiver_state": "ok", "receiver_updated_at": now.isoformat()}
        model.last_location = {"lat": 1.2, "lng": 3.4, "at": now.isoformat()}
        db.add(ShipmentModel(id="shipment", journey_id=journey_id, status="in_transit", updated_at=now))
        for state in ("uploading", "queued", "failed"):
            db.add(RecordingModel(id=state, vehicle_id=vehicle["id"], recorded_at=now,
                upload_state=state, processing_state="processing" if state == "uploading" else "pending", updated_at=now))
        db.add(RecordingModel(id="yesterday", vehicle_id=vehicle["id"], recorded_at=now - timedelta(days=1),
            upload_state="uploaded", processing_state="completed", updated_at=now))
        db.add(DriverRecordModel(id="alert", driver_id=driver["id"], journey_id=journey_id,
            kind="alert", title="Interference", severity="critical", status="open", at=now, updated_at=now))
        db.add(DriverRecordModel(id="incident", driver_id=driver["id"], journey_id=journey_id,
            kind="incident", title="Investigation", severity="high", status="awaiting_review", at=now, updated_at=now))
        db.add(DeviceIssueModel(id="issue", vehicle_id=vehicle["id"], kind="sync_delayed", device="Phone",
            detail="Sync delayed", since=now, updated_at=now))
        for kind in ("journey", "alert", "upload", "user", "incident"):
            db.add(ActivityModel(id=kind, at=now, actor="Operator", text=f"Updated {kind}", kind=kind))
        db.commit()
    return driver, vehicle, headers


def test_dashboard_aggregates_persisted_records(client, populated_dashboard):
    driver, vehicle, headers = populated_dashboard
    result = client.get("/api/v1/dashboard/summary", headers=headers)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["fleet"]["vehicles"] == data["fleet"]["drivers"] == 1
    assert data["fleet"]["vehiclesOnJourney"] == data["fleet"]["driversOnJourney"] == 1
    assert data["journeys"]["active"] == data["journeys"]["shipmentsInTransit"] == 1
    assert data["alerts"]["matrix"]["critical"]["open"] == 1
    assert data["gnss"]["receiversExpected"] == data["gnss"]["receiversReporting"] == 1
    assert data["gnss"]["recordingsToday"] == 3
    assert all(data["gnss"][key] == 1 for key in ("uploading", "queued", "failed", "processing"))
    assert data["activeJourneys"][0]["integrity"] == "alert_open"
    assert data["activeJourneys"][0]["lastLocationAt"] is not None
    assert data["devices"][0]["vehicle"] == vehicle["registration"]
    assert data["incidents"][0]["status"] == "awaiting_review"
    assert len(data["activity"]) == 5
    timeline = client.get(f"/api/v1/drivers/{driver['id']}", headers=headers)
    assert timeline.status_code == 200, timeline.text
    assert timeline.json()["incidents"][0]["status"] == "investigating"


def test_dashboard_server_redacts_nested_fields_and_activity(client, populated_dashboard, make_user, login_headers):
    user, _ = make_user(["dashboard:view"])
    headers = login_headers(user)
    data = client.get("/api/v1/dashboard/summary", headers=headers).json()
    for name in ("fleet", "journeys", "gnss"):
        assert data[name]["updatedAt"] is None
        assert all(value == 0 for key, value in data[name].items() if key != "updatedAt")
    assert all(value == 0 for statuses in data["alerts"]["matrix"].values() for value in statuses.values())
    assert data["devices"] == data["incidents"] == data["activity"] == data["activeJourneys"] == []
    assert data["devicesUpdatedAt"] is None
    user, _ = make_user(["dashboard:view", "journeys:view"])
    data = client.get("/api/v1/dashboard/summary", headers=login_headers(user)).json()
    assert data["journeys"]["active"] == 1
    assert data["journeys"]["shipmentsInTransit"] == 0
    assert data["activeJourneys"][0]["integrity"] == "not_assessed"
    assert data["activeJourneys"][0]["lastLocationAt"] is None
    assert data["activeJourneys"][0]["vehicle"] == data["activeJourneys"][0]["driver"] == ""
    assert [row["kind"] for row in data["activity"]] == ["journey"]
