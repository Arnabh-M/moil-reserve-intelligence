"""EquipmentStatusLog ORM model — append-only history of every equipment
status change (Field Intake Hardening §2.1). Additive only: `Equipment.status`
remains the single source of truth for current status; this table is history,
never a replacement read path.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.site import Site


class EquipmentStatusLog(Base):
    __tablename__ = "equipment_status_log"
    __table_args__ = (
        # Newest-first history lookups filter on equipment_id and order by
        # changed_at DESC — a composite index matching that access pattern.
        Index(
            "ix_equipment_status_log_equipment_id_changed_at",
            "equipment_id",
            text("changed_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("equipment.id"), index=True, nullable=False
    )
    # Denormalized so the site-wide history endpoint doesn't need a join.
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id"), index=True, nullable=False
    )
    old_status: Mapped[str | None] = mapped_column(String)
    new_status: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str | None] = mapped_column(String, server_default="system")
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    # 'manual' (single-row edit), 'bulk' (bulk-down flow), 'sync' (reserved
    # for a future automated ingestion path — not produced anywhere today).
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="manual")

    equipment: Mapped["Equipment"] = relationship()
    site: Mapped["Site"] = relationship()
