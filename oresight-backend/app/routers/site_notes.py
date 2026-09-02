"""Routes for free-text site notes + vector similarity ("RAG") search.

`POST /site-notes` embeds and stores a note; `GET /site-notes/search` embeds
the query and returns the nearest notes by cosine similarity (pgvector).
Embeddings are produced by app.services.embedding (deterministic + local by
default, swappable for a real model) — the route never sees raw vectors
beyond passing them to the DB.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SiteNote
from app.schemas import SiteNoteCreate, SiteNoteOut, SiteNoteSearchHit
from app.services.embedding import get_embedder
from app.services.lookups import get_site_or_404

logger = logging.getLogger("oresight.site_notes")

router = APIRouter(prefix="/site-notes", tags=["site-notes"])

DEFAULT_SEARCH_LIMIT = 5


def _note_to_out(note: SiteNote) -> SiteNoteOut:
    return SiteNoteOut(
        id=note.id, site_id=note.site_id, text=note.text, created_at=note.created_at
    )


@router.post("", response_model=SiteNoteOut, status_code=201, summary="Add a site note")
def create_site_note(
    payload: SiteNoteCreate, db: Session = Depends(get_db)
) -> SiteNoteOut:
    """Store a note and its auto-generated embedding.

    - Unknown `site_id` -> 404.
    - Blank text -> 422 (schema `min_length=1`).
    """
    get_site_or_404(db, payload.site_id)

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Note text must not be blank.")

    note = SiteNote(
        site_id=payload.site_id,
        text=text,
        embedding=get_embedder().embed(text),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _note_to_out(note)


@router.get(
    "/search",
    response_model=list[SiteNoteSearchHit],
    summary="Similarity search over site notes",
)
def search_site_notes(
    q: str = Query(..., min_length=1, description="Free-text query"),
    site_id: int | None = Query(None, description="Restrict the search to one site"),
    limit: int = Query(DEFAULT_SEARCH_LIMIT, ge=1, le=20),
    db: Session = Depends(get_db),
) -> list[SiteNoteSearchHit]:
    """Return the `limit` notes most similar to `q` by cosine similarity,
    best first. Empty result (no notes, or none for the given site) is a
    normal 200 `[]`, not an error.

    - Query that is only whitespace -> 400.
    - Unknown `site_id` -> 404.
    """
    query_text = q.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Query must not be empty.")
    if site_id is not None:
        get_site_or_404(db, site_id)

    q_vec = get_embedder().embed(query_text)
    distance = SiteNote.embedding.cosine_distance(q_vec).label("distance")

    stmt = select(SiteNote, distance).order_by(distance).limit(limit)
    if site_id is not None:
        stmt = stmt.where(SiteNote.site_id == site_id)

    rows = db.execute(stmt).all()
    return [
        SiteNoteSearchHit(
            id=note.id,
            site_id=note.site_id,
            text=note.text,
            created_at=note.created_at,
            relevance=round(max(0.0, 1.0 - float(dist)), 4),
        )
        for note, dist in rows
    ]
