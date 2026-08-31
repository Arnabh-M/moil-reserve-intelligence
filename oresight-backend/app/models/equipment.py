"""Equipment ORM model — per-machine up/down status at a site."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.site import Site


class EquipmentStatus(str, enum.Enum):
    UP = "up"
    DOWN = "down"


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    equipment_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EquipmentStatus] = mapped_column(
        Enum(
            EquipmentStatus,
            name="equipment_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=EquipmentStatus.UP,
    )
    last_status_change: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    status_reason: Mapped[str | None] = mapped_column(Text)

    site: Mapped["Site"] = relationship(back_populates="equipment")
