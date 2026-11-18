from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class DriverModel(Base):
    __tablename__ = "drivers"
    __table_args__ = (
        CheckConstraint("email = lower(trim(email)) AND length(email) > 0",
                        name="driver_email_normalized"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str] = mapped_column(String(32), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VehicleModel(Base):
    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    registration: Mapped[str] = mapped_column(String(12), unique=True)
    type: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(16))
    driver_id: Mapped[str | None] = mapped_column(ForeignKey("drivers.id"), unique=True)
    receiver_id: Mapped[str | None] = mapped_column(String(150), unique=True)
    device: Mapped[dict | None] = mapped_column(JSON)
    last_location: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MobileAccountModel(Base):
    __tablename__ = "mobile_accounts"

    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credential_version: Mapped[int] = mapped_column(Integer, default=1)


class JourneyModel(Base):
    __tablename__ = "journeys"
    __table_args__ = (
        Index("uq_live_journey_vehicle", "vehicle_id", unique=True,
              postgresql_where=text("status IN ('active', 'delayed')"),
              sqlite_where=text("status IN ('active', 'delayed')")),
        Index("uq_live_journey_driver", "driver_id", unique=True,
              postgresql_where=text("status IN ('active', 'delayed')"),
              sqlite_where=text("status IN ('active', 'delayed')")),
        CheckConstraint("progress >= 0 AND progress <= 100", name="journey_progress_range"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), index=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), index=True)
    route: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16))
    planned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    progress: Mapped[float] = mapped_column(Float, default=0)
    integrity: Mapped[str] = mapped_column(String(32), default="not_assessed")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DriverRecordModel(Base):
    __tablename__ = "driver_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"), index=True)
    journey_id: Mapped[str] = mapped_column(ForeignKey("journeys.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
