from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text

@pytest.mark.parametrize("legacy", [False, True])
def test_migration_handles_fresh_and_legacy_database(tmp_path, monkeypatch, legacy):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    if legacy:
        with engine.begin() as db:
            db.execute(text("CREATE TABLE users (id INTEGER NOT NULL PRIMARY KEY, full_name VARCHAR(150) NOT NULL, "
                            "email VARCHAR(255) NOT NULL UNIQUE, hashed_password VARCHAR(255) NOT NULL, "
                            "is_active BOOLEAN NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"))
            db.execute(text("INSERT INTO users (id, full_name, email, hashed_password, is_active) "
                            "VALUES (1, 'Original User', 'original@example.com', 'original_hash', false)"))
            db.execute(text("CREATE INDEX ix_users_id ON users (id)"))
            db.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email)"))
    monkeypatch.setattr("app.infrastructure.database.connection.engine", engine)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    tables = set(inspect(engine).get_table_names())
    assert "vehicles" in tables
    assert not tables.intersection({"email_outbox", "password_reset_tokens", "mfa_challenges"})
    assert "mfa_enabled" not in {column["name"] for column in inspect(engine).get_columns("users")}
    assert "username" not in {column["name"] for column in inspect(engine).get_columns("mobile_accounts")}
    assert next(column for column in inspect(engine).get_columns("drivers") if column["name"] == "email")["nullable"] is False
    if legacy:
        with engine.connect() as db:
            row = db.execute(text("SELECT full_name, hashed_password, status FROM users WHERE id = 1")).one()
            assert tuple(row) == ("Original User", "original_hash", "inactive")
    command.check(config)
    command.downgrade(config, "base")
    assert "vehicles" not in inspect(engine).get_table_names()
    assert "users" in inspect(engine).get_table_names()
    engine.dispose()


def test_remove_email_flows_from_existing_database(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'existing.db'}")
    monkeypatch.setattr("app.infrastructure.database.connection.engine", engine)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "0001_frontend_contract")
    with engine.begin() as db:
        for identifier, mfa in ((1, True), (2, False)):
            db.execute(text(
                "INSERT INTO users (id, full_name, email, hashed_password, is_active, mfa_enabled) "
                "VALUES (:id, 'Existing User', :email, 'existing_hash', true, :mfa)"
            ), {"id": identifier, "email": f"user{identifier}@example.com", "mfa": mfa})
            db.execute(text(
                "INSERT INTO access_sessions (token_hash, user_id, expires_at) "
                "VALUES (:token, :id, '2099-01-01')"
            ), {"token": f"token-{identifier}", "id": identifier})
        db.execute(text(
            "INSERT INTO password_reset_tokens (token_hash, user_id, expires_at) "
            "VALUES ('reset-token', 1, '2099-01-01')"
        ))
        db.execute(text(
            "INSERT INTO mfa_challenges (id, user_id, expires_at, secret_hash, attempts) "
            "VALUES ('challenge', 1, '2099-01-01', 'code-hash', 0)"
        ))
        db.execute(text(
            "INSERT INTO email_outbox "
            "(id, recipient, subject, body, created_at, attempts, next_attempt_at, expires_at) "
            "VALUES ('email', 'user1@example.com', 'Code', 'Secret', '2026-01-01', 0, '2026-01-01', '2099-01-01')"
        ))
    command.upgrade(config, "head")
    command.check(config)
    tables = set(inspect(engine).get_table_names())
    assert not tables.intersection({"email_outbox", "password_reset_tokens", "mfa_challenges"})
    with engine.connect() as db:
        assert db.execute(text("SELECT id, hashed_password FROM users ORDER BY id")).all() == [
            (1, "existing_hash"), (2, "existing_hash"),
        ]
        assert db.execute(text("SELECT token_hash FROM access_sessions")).scalars().all() == ["token-2"]
    command.downgrade(config, "0001_frontend_contract")
    assert {"email_outbox", "password_reset_tokens", "mfa_challenges"}.issubset(inspect(engine).get_table_names())
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()


@pytest.fixture
def email_login_database(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'driver-email.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    monkeypatch.setattr("app.infrastructure.database.connection.engine", engine)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "0002_remove_email_flows")
    yield engine, config
    engine.dispose()


def legacy_driver(db, identifier, email):
    db.execute(text(
        "INSERT INTO drivers (id, name, phone, email, status, updated_at) "
        "VALUES (:id, 'Existing Driver', :phone, :email, 'active', '2026-01-01')"
    ), {"id": identifier, "phone": identifier, "email": email})


def test_driver_email_migration_preserves_mobile_account(email_login_database):
    engine, config = email_login_database
    email = "a-driver-with-a-long-email-address@example.com"
    with engine.begin() as db:
        legacy_driver(db, "d1", f" {email.upper()} ")
        db.execute(text(
            "INSERT INTO mobile_accounts "
            "(driver_id, username, password_hash, active, must_change_password, created_at, last_login_at, credential_version) "
            "VALUES ('d1', 'old.username', 'existing_hash', true, false, '2026-01-01', '2026-01-02', 7)"
        ))
        db.execute(text(
            "INSERT INTO vehicles (id, registration, type, model, status, driver_id, updated_at) "
            "VALUES ('v1', 'ABC-123', 'truck', 'Truck', 'active', 'd1', '2026-01-01')"
        ))
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as db:
        assert db.execute(text("SELECT email FROM drivers WHERE id = 'd1'")).scalar_one() == email
        assert tuple(db.execute(text(
            "SELECT password_hash, active, must_change_password, credential_version FROM mobile_accounts"
        )).one()) == ("existing_hash", True, False, 8)
        assert db.execute(text("SELECT last_login_at FROM mobile_accounts")).scalar_one() == "2026-01-02"
        assert db.execute(text("SELECT driver_id FROM vehicles")).scalar_one() == "d1"
        assert db.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert db.execute(text("PRAGMA foreign_key_check")).all() == []
    assert "username" not in {column["name"] for column in inspect(engine).get_columns("mobile_accounts")}
    command.downgrade(config, "0002_remove_email_flows")
    with engine.connect() as db:
        username = db.execute(text("SELECT username FROM mobile_accounts")).scalar_one()
        assert len(username) == 32
        assert db.execute(text("SELECT password_hash FROM mobile_accounts")).scalar_one() == "existing_hash"
    command.upgrade(config, "head")
    command.check(config)


@pytest.mark.parametrize("email", [None, "", " ", "invalid", " DUPLICATE@example.com "])
def test_driver_email_migration_requires_clean_data_before_changes(email_login_database, email):
    engine, config = email_login_database
    with engine.begin() as db:
        legacy_driver(db, "d1", "duplicate@example.com")
        legacy_driver(db, "d2", email)
    with pytest.raises(RuntimeError, match="before migration"):
        command.upgrade(config, "head")
    # Validation must not discard legacy usernames or partially normalize driver data.
    assert "username" in {column["name"] for column in inspect(engine).get_columns("mobile_accounts")}
    with engine.begin() as db:
        assert db.execute(text("SELECT email FROM drivers WHERE id = 'd2'")).scalar_one() == email
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0002_remove_email_flows"
        assert db.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        db.execute(text("UPDATE drivers SET email = 'corrected@example.com' WHERE id = 'd2'"))
    command.upgrade(config, "head")
    command.check(config)
