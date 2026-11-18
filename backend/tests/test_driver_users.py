import pytest
from sqlalchemy import select

from app.domain.authentication.permissions import DRIVER_ROLE_ID
from app.infrastructure.database.models.access_model import user_roles
from app.infrastructure.database.models.fleet_model import DriverModel
from app.infrastructure.database.models.user_model import UserModel
from tests.conftest import PASSWORD


@pytest.fixture
def driver_login(client, admin):
    _, _, headers = admin
    result = client.post("/api/v1/drivers", headers=headers, json={
        "name": "Driver One", "phone": "123456789", "email": "driver@example.com",
    })
    assert result.status_code == 201, result.text
    driver = result.json()
    issued = client.post(f"/api/v1/drivers/{driver['id']}/credentials", headers=headers)
    assert issued.status_code == 201, issued.text
    credentials = issued.json()
    login = client.post("/api/v1/auth/login", json={
        "email": credentials["email"], "password": credentials["temporaryPassword"],
    })
    assert login.status_code == 200, login.text
    return credentials, login.json(), headers


def auth(session):
    return {"Authorization": "Bearer " + session["token"]}


def change_password(client, credentials, session):
    response = client.post("/api/v1/auth/change-password", headers=auth(session), json={
        "currentPassword": credentials["temporaryPassword"], "newPassword": PASSWORD,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_driver_identity_is_a_user_with_restricted_first_login(client, driver_login, db_factory):
    credentials, session, admin_headers = driver_login
    account = credentials["driver"]["userAccount"]
    driver_id = credentials["driver"]["id"]
    assert session["user"]["id"] == account["id"]
    assert session["user"]["driverId"] == driver_id
    assert session["user"]["mustChangePassword"] is True
    assert session["permissions"] == []
    assert session["roleNames"] == ["Driver"]
    assert client.get("/api/v1/auth/me", headers=auth(session)).json() == session["user"]
    assert client.get("/api/v1/users", headers=auth(session)).json()["code"] == "password_change_required"
    users = client.get("/api/v1/users", headers=admin_headers).json()
    assert next(user for user in users if user["id"] == account["id"])["driverId"] == driver_id
    with db_factory() as db:
        assert db.get(DriverModel, driver_id).user_id == int(account["id"])
        assert list(db.scalars(select(user_roles.c.role_id).where(
            user_roles.c.user_id == int(account["id"])
        ))) == [DRIVER_ROLE_ID]
    renewed = change_password(client, credentials, session)
    assert renewed["user"]["mustChangePassword"] is False
    assert renewed["permissions"] == ["driver:access"]
    assert client.get("/api/v1/auth/me", headers=auth(session)).status_code == 401
    for path in ("/users", "/roles", "/drivers", "/vehicles", "/dashboard/summary"):
        assert client.get("/api/v1" + path, headers=auth(renewed)).status_code == 403


def test_password_change_requires_current_password_and_strength(client, driver_login):
    credentials, session, _ = driver_login
    for current, password, status in (
        ("wrong", PASSWORD, 422),
        (credentials["temporaryPassword"], "weak", 422),
        (credentials["temporaryPassword"], credentials["temporaryPassword"], 422),
    ):
        assert client.post("/api/v1/auth/change-password", headers=auth(session), json={
            "currentPassword": current, "newPassword": password,
        }).status_code == status
    assert client.get("/api/v1/auth/me", headers=auth(session)).json()["mustChangePassword"] is True


def test_reset_revoke_and_deactivation_invalidate_shared_sessions(client, driver_login):
    credentials, session, headers = driver_login
    current = change_password(client, credentials, session)
    path = "/api/v1/drivers/" + credentials["driver"]["id"]
    reset = client.post(path + "/credentials/reset-password", headers=headers)
    assert reset.status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth(current)).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": credentials["email"], "password": PASSWORD}).status_code == 401
    password = reset.json()["temporaryPassword"]
    login = client.post("/api/v1/auth/login", json={"email": credentials["email"], "password": password}).json()
    assert client.delete(path + "/credentials", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=auth(login)).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": credentials["email"], "password": password}).status_code == 403
    assert client.get(path, headers=headers).json()["driver"]["userAccount"]["id"] == credentials["driver"]["userAccount"]["id"]
    assert client.post(path + "/status", headers=headers, json={"status": "inactive"}).status_code == 200
    user_id = credentials["driver"]["userAccount"]["id"]
    assert client.patch(f"/api/v1/users/{user_id}", headers=headers, json={"status": "active"}).status_code == 409


def test_linked_users_cannot_gain_staff_roles_or_diverge_from_driver(client, driver_login, admin):
    credentials, _, headers = driver_login
    _, role, _ = admin
    user_id = credentials["driver"]["userAccount"]["id"]
    for changes in ({"roleIds": [role.id]}, {"email": "other@example.com"}, {"name": "Other"}):
        assert client.patch(f"/api/v1/users/{user_id}", headers=headers, json=changes).status_code == 409
    role_body = {"name": "Driver", "description": "Escalation", "permissions": ["users:manage"]}
    assert client.put(f"/api/v1/roles/{DRIVER_ROLE_ID}", headers=headers, json=role_body).status_code == 409
    assert client.post("/api/v1/users", headers=headers, json={
        "name": "Unlinked", "email": "unlinked@example.com", "roleIds": [DRIVER_ROLE_ID], "password": PASSWORD,
    }).status_code == 422


def test_existing_staff_email_is_never_silently_linked_or_overwritten(client, admin, db_factory):
    user, _, headers = admin
    driver = client.post("/api/v1/drivers", headers=headers, json={
        "name": "Matching Driver", "phone": "123456789", "email": user.email,
    }).json()
    result = client.post(f"/api/v1/drivers/{driver['id']}/credentials", headers=headers)
    assert result.status_code == 409
    with db_factory() as db:
        assert db.get(DriverModel, driver["id"]).user_id is None
        assert db.get(UserModel, user.id).hashed_password == user.hashed_password
    assert client.get("/api/v1/users", headers=headers).status_code == 200


def test_email_edits_sync_user_and_revoke_driver_sessions(client, driver_login):
    credentials, session, headers = driver_login
    current = change_password(client, credentials, session)
    driver = credentials["driver"]
    result = client.put(f"/api/v1/drivers/{driver['id']}", headers=headers, json={
        "name": "Updated Driver", "phone": driver["phone"], "email": "new@example.com",
    })
    assert result.status_code == 200
    assert result.json()["userAccount"]["email"] == "new@example.com"
    assert client.get("/api/v1/auth/me", headers=auth(current)).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "new@example.com", "password": PASSWORD}).json()["user"]["name"] == "Updated Driver"


@pytest.mark.parametrize("from_profile", [False, True])
def test_user_or_driver_deactivation_revokes_session(client, driver_login, from_profile):
    credentials, session, headers = driver_login
    current = change_password(client, credentials, session)
    driver = credentials["driver"]
    if from_profile:
        response = client.post(f"/api/v1/drivers/{driver['id']}/status", headers=headers, json={"status": "inactive"})
    else:
        response = client.patch(f"/api/v1/users/{current['user']['id']}", headers=headers, json={"status": "inactive"})
    assert response.status_code == 200, response.text
    assert client.get("/api/v1/auth/me", headers=auth(current)).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": credentials["email"], "password": PASSWORD}).status_code == 403
    detail = client.get(f"/api/v1/drivers/{driver['id']}", headers=headers).json()["driver"]
    assert detail["userAccount"]["status"] == "inactive"
    if from_profile:
        assert client.post(f"/api/v1/drivers/{driver['id']}/status", headers=headers, json={"status": "active"}).status_code == 200
        # Operational activation does not silently restore revoked login access.
        assert client.post("/api/v1/auth/login", json={"email": credentials["email"], "password": PASSWORD}).status_code == 403


def test_linked_driver_email_cannot_overwrite_staff_identity(client, driver_login, admin):
    credentials, session, headers = driver_login
    staff, _, _ = admin
    driver = credentials["driver"]
    response = client.put(f"/api/v1/drivers/{driver['id']}", headers=headers, json={
        "name": "Should roll back", "phone": driver["phone"], "email": staff.email,
    })
    assert response.status_code == 409
    persisted = client.get(f"/api/v1/drivers/{driver['id']}", headers=headers).json()["driver"]
    assert persisted["name"] == driver["name"]
    assert persisted["email"] == persisted["userAccount"]["email"] == credentials["email"]
    assert client.get("/api/v1/auth/me", headers=auth(session)).status_code == 200
