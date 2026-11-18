from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.errors import install_error_handlers
from app.infrastructure.database.connection import engine
from app.presentation.access.router import router as access_router
from app.presentation.authentication.router import router as auth_router
from app.presentation.dashboard.router import router as dashboard_router
from app.presentation.fleet.router import router as fleet_router


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        description="Backend API for SignalShield Cargo",
        version="1.0.0",
    )
    install_error_handlers(application)
    for router in (auth_router, access_router, fleet_router, dashboard_router):
        application.include_router(router, prefix=settings.API_PREFIX)

    @application.get("/")
    def root():
        return {"message": "SignalShield Cargo Backend is running!"}

    @application.get("/health")
    def health():
        return {"status": "healthy"}

    @application.get("/health/database")
    def database_health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "connected", "database": engine.dialect.name}

    return application


api = create_app()
# Wrap the complete app, including error responses, so browser clients can read errors.
app = CORSMiddleware(
    api,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
