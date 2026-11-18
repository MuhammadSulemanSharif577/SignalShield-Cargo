from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ShipmentModel(Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    journey_id: Mapped[str | None] = mapped_column(ForeignKey("journeys.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RecordingModel(Base):
    __tablename__ = "gnss_recordings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    upload_state: Mapped[str] = mapped_column(String(16), index=True)
    processing_state: Mapped[str] = mapped_column(String(16), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DeviceIssueModel(Base):
    __tablename__ = "device_issues"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    device: Mapped[str] = mapped_column(String(150))
    detail: Mapped[str] = mapped_column(Text)
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ActivityModel(Base):
    __tablename__ = "activity"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor: Mapped[str] = mapped_column(String(150))
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16), index=True)
