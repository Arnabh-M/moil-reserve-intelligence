"""SiteNote ORM model — free-text field notes per site, with a vector
embedding for similarity ("RAG") search.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.services.embedding import EMBEDDING_DIM

if TYPE_CHECKING:
    from app.models.site import Site


class SiteNote(Base):
    __tablename__ = "site_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True, nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # Groundwork for a future PATCH /site-notes/{id} (Field Intake Hardening
    # §6): no update path exists yet, so these are unused today, but a
    # future update endpoint can require a matching `revision` to guard
    # against overwriting a note that changed since it was read.
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )

    site: Mapped["Site"] = relationship(back_populates="site_notes")
