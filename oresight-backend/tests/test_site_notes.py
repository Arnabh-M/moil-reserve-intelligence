"""Tests for POST /site-notes and GET /site-notes/search (pgvector RAG).

Embedder unit tests need no infra. Endpoint tests hit the real stack and
SKIP when Postgres is unreachable. Notes created by a test are deleted on
teardown; the 15 seeded demo notes are left alone.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import SiteNote
from app.services.embedding import EMBEDDING_DIM, HashingEmbedder

# --------------------------------------------------------------------------
# embedder unit tests (no infra)
# --------------------------------------------------------------------------

EMB = HashingEmbedder()


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def test_embedding_has_fixed_dim_and_is_unit_norm():
    v = EMB.embed("haul road washed out by monsoon rain")
    assert len(v) == EMBEDDING_DIM
    assert abs(sum(x * x for x in v) ** 0.5 - 1.0) < 1e-6


def test_embedding_is_deterministic():
    assert EMB.embed("Excavator NAG-1 hydraulic fault") == EMB.embed("Excavator NAG-1 hydraulic fault")


def test_embedding_related_text_scores_higher_than_unrelated():
    q = EMB.embed("hydraulic pump failure on the excavator")
    related = EMB.embed("Excavator NAG-1 hydraulic fault recurred; pump being rebuilt")
    unrelated = EMB.embed("community liaison meeting about approach-road dust")
    assert _cos(q, related) > _cos(q, unrelated)


def test_embedding_empty_text_is_defined_not_nan():
    v = EMB.embed("   ...  ")
    assert len(v) == EMBEDDING_DIM
    assert abs(sum(v) - 1.0) < 1e-6  # the deterministic fallback unit vector


# --------------------------------------------------------------------------
# endpoint tests (need Postgres + pgvector)
# --------------------------------------------------------------------------


def _postgres_reachable() -> bool:
    try:
        engine = create_engine(
            get_settings().DATABASE_URL, connect_args={"connect_timeout": 3}
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except SQLAlchemyError:
        return False


@pytest.fixture(scope="module")
def client():
    if not _postgres_reachable():
        pytest.skip("Postgres is not reachable (is `docker compose up -d` running?)")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def created_note_ids():
    ids: list[int] = []
    yield ids
    if ids:
        db = SessionLocal()
        db.execute(delete(SiteNote).where(SiteNote.id.in_(ids)))
        db.commit()
        db.close()


def test_create_note_then_find_it_as_top_hit(client, created_note_ids):
    marker = "Rockfall onto the tertiary crusher feed chute during the graveyard shift; area barricaded."
    r = client.post("/site-notes", json={"site_id": 3, "text": marker})
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "site_id", "text", "created_at"}
    created_note_ids.append(body["id"])

    hits = client.get("/site-notes/search", params={"q": "rockfall on the crusher feed chute"}).json()
    assert hits
    assert hits[0]["id"] == body["id"]
    assert hits[0]["text"] == marker
    assert 0.0 <= hits[0]["relevance"] <= 1.0


def test_create_rejects_unknown_site(client):
    r = client.post("/site-notes", json={"site_id": 99999, "text": "note for a site that does not exist"})
    assert r.status_code == 404
    assert r.json()["error_code"] == "NOT_FOUND"


def test_create_rejects_blank_text(client):
    assert client.post("/site-notes", json={"site_id": 1, "text": ""}).status_code == 422
    assert client.post("/site-notes", json={"site_id": 1, "text": "    "}).status_code == 422


def test_search_requires_q(client):
    assert client.get("/site-notes/search").status_code == 422


def test_search_blank_q_is_400(client):
    assert client.get("/site-notes/search", params={"q": "   "}).status_code == 400


def test_search_unknown_site_is_404(client):
    r = client.get("/site-notes/search", params={"q": "rain", "site_id": 99999})
    assert r.status_code == 404


def test_search_is_ranked_and_respects_limit(client):
    hits = client.get(
        "/site-notes/search", params={"q": "equipment breakdown", "limit": 3}
    ).json()
    assert 1 <= len(hits) <= 3
    relevances = [h["relevance"] for h in hits]
    assert relevances == sorted(relevances, reverse=True)
    assert all(0.0 <= r <= 1.0 for r in relevances)


def test_search_site_filter_restricts_results(client):
    hits = client.get(
        "/site-notes/search", params={"q": "rain", "site_id": 2}
    ).json()
    assert hits, "seed notes exist for site 2"
    assert {h["site_id"] for h in hits} == {2}
