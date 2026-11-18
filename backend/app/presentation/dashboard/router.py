from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.authentication.use_cases.access_service import Principal
from app.application.dashboard.schemas import DashboardSnapshot
from app.application.dashboard.use_cases.summary import DashboardSummary
from app.infrastructure.database.connection import get_db
from app.infrastructure.repositories.dashboard_repository_implementation import SQLAlchemyDashboardRepository
from app.presentation.authentication.dependencies import require_permissions

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSnapshot)
def summary(principal: Principal = Depends(require_permissions("dashboard:view")), db: Session = Depends(get_db)):
    return DashboardSummary(SQLAlchemyDashboardRepository(db)).execute(principal)
