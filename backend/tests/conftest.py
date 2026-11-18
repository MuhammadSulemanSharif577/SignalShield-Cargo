import os
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "integration-test-secret"

import pytest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.domain.authentication.entities.access import Role
from app.domain.authentication.entities.user import User
from app.domain.authentication.permissions import DRIVER_ROLE_ID, PERMISSIONS
from app.infrastructure.database.base import Base
from app.infrastructure.database.connection import get_db
from app.infrastructure.repositories.access_repository_implementation import SQLAlchemyAccessRepository
from app.main import create_app

PASSWORD = "SecurePassword123"


@pytest.fixture
def db_factory():
    url = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    options = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, **options)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        if engine.dialect.name == "sqlite":
            connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        SQLAlchemyAccessRepository(db).save_role(Role(
            DRIVER_ROLE_ID, "Driver", "Driver account; no staff or fleet-wide access.",
            ["driver:access"], True, ["driver:access"],
        ))
        db.commit()
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_factory):
    api = create_app()

    def override_db():
        with db_factory() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    api.dependency_overrides[get_db] = override_db
    app = CORSMiddleware(api, allow_origins=["http://localhost:3000"],
                         allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                         allow_headers=["Authorization", "Content-Type"])
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def make_user(db_factory):
    def create(permissions=None, *, email=None, status="active", built_in=False):
        with db_factory() as db:
            repository = SQLAlchemyAccessRepository(db)
            role = Role(str(uuid4()), "Role " + str(uuid4()), "Test role",
                        sorted(PERMISSIONS if permissions is None else permissions), built_in,
                        ["users:manage", "roles:manage"] if built_in else [])
            repository.save_role(role)
            user = User(None, "Test User", email or f"{uuid4()}@example.com", hash_password(PASSWORD),
                        status=status, role_ids=[role.id])
            repository.save_user(user)
            repository.commit()
            return user, role
    return create


@pytest.fixture
def login_headers(client):
    def login(user, password=PASSWORD):
        result = client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
        assert result.status_code == 200, result.text
        return {"Authorization": "Bearer " + result.json()["token"]}
    return login


@pytest.fixture
def admin(make_user, login_headers):
    user, role = make_user(built_in=True)
    return user, role, login_headers(user)
