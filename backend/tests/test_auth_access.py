from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import verify_password
from app.core.time import utcnow
from app.infrastructure.database.models.access_model import (
    RoleModel, SessionModel,
)
from app.infrastructure.database.models.user_model import UserModel
from tests.conftest import PASSWORD


def test_session_rotation_revocation_and_current_permissions(client, admin, db_factory):
    user, role, headers = admin
    token = headers["Authorization"].split()[1]
    with db_factory() as db:
        assert db.get(SessionModel, token) is None  # Raw bearer tokens are never stored.
        model = db.get(RoleModel, role.id)
        model.permissions = ["users:view"]
        model.name = "Changed role"
        db.commit()
    result = client.post("/api/v1/auth/refresh", headers=headers)
    assert result.status_code == 200, result.text
    session = result.json()
    assert set(session) == {"token", "expiresAt", "user", "roleNames", "permissions"}
    assert datetime.fromisoformat(session["expiresAt"]).utcoffset() is not None
    assert session["user"] == {"id": str(user.id), "name": user.full_name, "email": user.email,
                               "driverId": None, "mustChangePassword": False}
    assert session["permissions"] == ["users:view"]
    assert session["roleNames"] == ["Changed role"]
    assert session["token"] != token
    assert client.get("/api/v1/users", headers=headers).status_code == 401
    renewed = {"Authorization": "Bearer " + session["token"]}
    assert client.get("/api/v1/users", headers=renewed).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=renewed).content == b""
    assert client.get("/api/v1/users", headers=renewed).status_code == 401


@pytest.mark.parametrize("path, body", [
    ("/forgot-password", {"email": "user@example.com"}),
    ("/reset-password", {"token": "old-token", "newPassword": PASSWORD}),
    ("/mfa/verify", {"challengeId": "old-challenge", "code": "123456"}),
])
def test_email_auth_routes_are_removed(client, path, body):
    response = client.post("/api/v1/auth" + path, json=body)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert "/api/v1/auth" + path not in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize("status", ["inactive", "pending"])
def test_login_account_states(client, make_user, status):
    user, _ = make_user(status=status)
    result = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert result.status_code == 403
    assert result.json()["code"] == status


def test_login_lockout(client, make_user):
    user, _ = make_user()
    for _ in range(settings.LOGIN_MAX_ATTEMPTS):
        assert client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrong"}).status_code == 401
    locked = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert locked.status_code == 403
    assert locked.json()["code"] == "locked"


def test_expired_sessions_are_rejected(client, make_user, login_headers, db_factory):
    user, _ = make_user()
    headers = login_headers(user)
    with db_factory() as db:
        db.scalar(select(SessionModel)).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.post("/api/v1/auth/refresh", headers=headers).status_code == 401


def test_user_provisioning_with_initial_password_and_activation(client, admin, db_factory):
    _, role, headers = admin
    body = {"name": "New Operator", "email": "new@example.com", "roleIds": [role.id], "password": PASSWORD}
    result = client.post("/api/v1/users", json=body, headers=headers)
    assert result.status_code == 201, result.text
    user = result.json()
    assert set(user) == {"id", "name", "email", "roleIds", "status", "lastLogin", "driverId", "mustChangePassword"}
    assert user["status"] == "pending" and user["lastLogin"] is None
    assert isinstance(user["id"], str)
    with db_factory() as db:
        model = db.get(UserModel, int(user["id"]))
        assert model.status == "pending"
        assert model.hashed_password != PASSWORD
        assert verify_password(PASSWORD, model.hashed_password)
    assert client.post("/api/v1/auth/login", json={"email": user["email"], "password": PASSWORD}).json()["code"] == "pending"
    activated = client.patch(f"/api/v1/users/{user['id']}", json={"status": "active"}, headers=headers)
    assert activated.status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": user["email"], "password": PASSWORD}).status_code == 200
    activity = client.get("/api/v1/dashboard/summary", headers=headers).json()["activity"]
    assert any(item["text"] == "Created user New Operator." and item["kind"] == "user" for item in activity)
    duplicate = client.post("/api/v1/users", json={**body, "email": "NEW@example.com"}, headers=headers)
    assert duplicate.status_code == 409
    users = client.get("/api/v1/users", headers=headers).json()
    assert all("password" not in item and "hashedPassword" not in item for item in users)


@pytest.mark.parametrize("password", ["weak", "alllowercase123", "ALLUPPERCASE123", "NoDigitsHere"])
def test_user_provisioning_rejects_weak_passwords(client, admin, password, db_factory):
    _, role, headers = admin
    result = client.post("/api/v1/users", headers=headers, json={
        "name": "New Operator", "email": "new@example.com", "roleIds": [role.id], "password": password,
    })
    assert result.status_code == 422 and result.json()["code"] == "weak_password"
    with db_factory() as db:
        assert db.scalar(select(UserModel).where(UserModel.email == "new@example.com")) is None


def test_user_provisioning_requires_password_and_rejects_mfa(client, admin):
    user, role, headers = admin
    body = {"name": "New Operator", "email": "new@example.com", "roleIds": [role.id]}
    assert client.post("/api/v1/users", headers=headers, json=body).status_code == 422
    assert client.post("/api/v1/users", headers=headers, json={
        **body, "password": PASSWORD, "mfaEnabled": True,
    }).status_code == 422
    assert client.patch(f"/api/v1/users/{user.id}", headers=headers, json={"mfaEnabled": True}).status_code == 422


def test_initial_password_preserves_whitespace(client, admin):
    _, role, headers = admin
    password = " " + PASSWORD + " "
    response = client.post("/api/v1/users", headers=headers, json={
        "name": "New Operator", "email": "new@example.com", "roleIds": [role.id], "password": password,
    })
    assert response.status_code == 201, response.text
    identifier = response.json()["id"]
    assert client.patch(f"/api/v1/users/{identifier}", headers=headers, json={"status": "active"}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "new@example.com", "password": password}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "new@example.com", "password": PASSWORD}).status_code == 401


def test_user_patch_self_protection_and_validation(client, admin):
    user, _, headers = admin
    for body in ({"status": "inactive"}, {"status": "pending"}):
        assert client.patch(f"/api/v1/users/{user.id}", json=body, headers=headers).status_code == 409
    for body in ({"roleIds": []}, {"name": None}, {"roleIds": ["missing"]}, {"status": "bad"}):
        result = client.patch(f"/api/v1/users/{user.id}", json=body, headers=headers)
        assert result.status_code == 422
        assert result.json()["code"] == "validation"
    assert client.patch("/api/v1/users/opaque-missing", json={}, headers=headers).status_code == 404


def test_role_metadata_uniqueness_and_deletion_rules(client, admin):
    _, built_in, headers = admin
    body = {"name": "Observers", "description": "Read operations", "permissions": ["dashboard:view"]}
    result = client.post("/api/v1/roles", json=body, headers=headers)
    assert result.status_code == 201, result.text
    role = result.json()
    assert role["builtIn"] is False and role["lockedPermissions"] == [] and role["userCount"] == 0
    assert client.post("/api/v1/roles", json={**body, "name": "OBSERVERS"}, headers=headers).status_code == 409
    assert client.put(f"/api/v1/roles/{built_in.id}", json=body, headers=headers).status_code == 409
    assert client.delete(f"/api/v1/roles/{built_in.id}", headers=headers).status_code == 409
    created = client.post("/api/v1/users", headers=headers, json={
        "name": "Observer", "email": "observer@example.com", "roleIds": [role["id"]], "password": PASSWORD,
    }).json()
    roles = client.get("/api/v1/roles", headers=headers).json()
    assert next(row for row in roles if row["id"] == role["id"])["userCount"] == 1
    assert client.delete(f"/api/v1/roles/{role['id']}", headers=headers).status_code == 409
    assert client.patch(f"/api/v1/users/{created['id']}", headers=headers, json={"roleIds": [built_in.id]}).status_code == 200
    assert client.delete(f"/api/v1/roles/{role['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/roles/{role['id']}", headers=headers).status_code == 404


def test_permissions_and_error_cors_shape(client, make_user, login_headers):
    user, _ = make_user(["users:view"])
    headers = login_headers(user)
    assert client.get("/api/v1/users", headers=headers).status_code == 200
    assert client.get("/api/v1/roles", headers=headers).status_code == 200
    assert client.post("/api/v1/roles", headers=headers, json={
        "name": "Forbidden", "description": "", "permissions": ["users:view"],
    }).status_code == 403
    for path in ("/api/v1/vehicles", "/api/v1/users", "/api/v1/dashboard/summary"):
        result = client.get(path, headers={"Origin": "http://localhost:3000"})
        assert result.status_code == 401
        assert set(result.json()) == {"code", "message"}
        assert result.headers["access-control-allow-origin"] == "http://localhost:3000"
    malformed = client.post("/api/v1/auth/login", json={"email": "bad", "password": ""})
    assert malformed.status_code == 422 and set(malformed.json()) == {"code", "message"}
    missing = client.get("/api/v1/not-a-route")
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"
    preflight = client.options("/api/v1/users", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    assert preflight.status_code == 200
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
        assert method in preflight.headers["access-control-allow-methods"]
