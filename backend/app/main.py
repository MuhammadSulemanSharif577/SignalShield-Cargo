
from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import settings

from app.infrastructure.database.connection import engine
from app.infrastructure.database.base import Base

# Import models so SQLAlchemy registers them with Base.metadata
from app.infrastructure.database.models.user_model import UserModel

from app.presentation.authentication.router import router as auth_router


app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for SignalShield Cargo shipment",
    version="1.0.0"
)


# DEVELOPMENT ONLY:
# Automatically creates database tables.
# Use Alembic migrations for managed schema changes.

Base.metadata.create_all(bind=engine)


# Register authentication routes

app.include_router(auth_router)


@app.get("/")
def root():

    return {
        "message": "SignalShield Cargo Backend is running!"
    }


@app.get("/health")
def health_check():

    return {
        "status": "healthy"
    }


@app.get("/health/database")
def database_health_check():

    try:

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "connected",
            "database": "PostgreSQL"
        }

    except Exception:

        return {
            "status": "disconnected",
            "database": "PostgreSQL"
        }
