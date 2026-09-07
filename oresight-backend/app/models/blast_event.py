"""BlastEvent ORM model — planned vs actual blasts, and why they slipped.

SIH26009 names blasting delays as a driver of production shortfall alongside
equipment downtime and weather. `delay_reason` is a native enum rather than
free text so it can later be aggregated into a shortfall-model feature.
"""

import enum
from datetime import date as date_, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.reserve_zone import ReserveZone
    from app.models.site import Site


class BlastStatus(str, enum.Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


class BlastDelayReason(str, enum.Enum):
    PERMIT_PENDING = "permit_pending"
    WEATHER_HOLD = "weather_hold"
    SAFETY_HOLD = "safety_hold"
    EQUIPMENT_UNAVAILABLE = "equipment_unavailable"
    EXPLOSIVE_SUPPLY = "explosive_supply"


class BlastEvent(Base):
    __tablename__ = "blast_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id"), index=True, nullable=False
    )
    reserve_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("reserve_zones.id", ondelete="SET NULL"), index=True
    )
    planned_date: Mapped[date_] = mapped_column(Date, nullable=False, index=True)
    actual_date: Mapped[date_ | None] = mapped_column(Date)
    status: Mapped[BlastStatus] = mapped_column(
        Enum(
            BlastStatus,
            name="blast_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=BlastStatus.PLANNED,
        server_default=BlastStatus.PLANNED.value,
    )
    delay_reason: Mapped[BlastDelayReason | None] = mapped_column(
        Enum(
            BlastDelayReason,
            name="blast_delay_reason",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    expected_yield_tonnes: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    actual_yield_tonnes: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    site: Mapped["Site"] = relationship(back_populates="blast_events")
    reserve_zone: Mapped["ReserveZone | None"] = relationship(
        back_populates="blast_events"
    )
