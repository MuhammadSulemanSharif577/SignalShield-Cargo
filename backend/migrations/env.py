from alembic import context

from app.infrastructure.database.base import Base
from app.infrastructure.database.connection import engine
from app.infrastructure.database import models  # noqa: F401

target_metadata = Base.metadata


def run_migrations():
    with engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            # Batch alterations rebuild parent tables; do not cascade-delete children.
            foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        try:
            context.configure(connection=connection, target_metadata=target_metadata,
                              render_as_batch=sqlite)
            with context.begin_transaction():
                context.run_migrations()
            if sqlite and connection.exec_driver_sql("PRAGMA foreign_key_check").first():
                raise RuntimeError("Migration left invalid foreign-key references.")
        finally:
            if sqlite:
                connection.rollback()
                connection.exec_driver_sql(f"PRAGMA foreign_keys={int(foreign_keys)}")
                connection.commit()


if context.is_offline_mode():
    raise RuntimeError("This migration inspects the legacy schema and requires a database connection.")
run_migrations()
