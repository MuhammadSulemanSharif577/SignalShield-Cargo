"""Run locking checks with TEST_DATABASE_URL pointing to an isolated PostgreSQL DB."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest


@pytest.fixture(autouse=True)
def require_postgres(db_factory):
    with db_factory() as db:
        if db.bind.dialect.name != "postgresql":
            pytest.skip("Row-locking checks require PostgreSQL")


def concurrently(operation):
    barrier = Barrier(2)

    def run(_):
        barrier.wait(timeout=5)
        return operation()

    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(run, range(2)))


def test_refresh_rotates_a_session_only_once(client, admin):
    _, _, headers = admin
    responses = concurrently(lambda: client.post("/api/v1/auth/refresh", headers=headers))
    assert sorted(response.status_code for response in responses) == [200, 401]


def test_driver_login_creation_is_serialized(client, admin):
    _, _, headers = admin
    created = client.post("/api/v1/drivers", headers=headers, json={
        "name": "Concurrent Driver", "phone": "1234567890", "email": "driver@example.com",
    })
    assert created.status_code == 201, created.text
    driver_id = created.json()["id"]
    responses = concurrently(lambda: client.post(f"/api/v1/drivers/{driver_id}/credentials", headers=headers))
    assert sorted(response.status_code for response in responses) == [201, 409]
