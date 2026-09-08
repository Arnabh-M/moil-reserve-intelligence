"""ProductionRecordAudit ORM model — append-only field-change log for
production_records PATCH edits (Field Intake Hardening §3.4).
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.production_record import ProductionRecord


class ProductionRecordAudit(Base):
    __tablename__ = "production_record_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(
        ForeignKey("production_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    field: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str | None] = mapped_column(String, server_default="system")
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    record: Mapped["ProductionRecord"] = relationship()
