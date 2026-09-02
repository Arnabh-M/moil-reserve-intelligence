"""Tests for POST /reports/upload — PDF -> deposit extraction -> Neo4j MERGE.

Extractor unit tests need no infra. The endpoint tests hit the real stack
and SKIP (not fail) when it's unreachable, matching the rest of the suite.
Anything written to Neo4j is deleted on teardown (every upload node carries
`source='report_upload'`, so cleanup is a one-liner).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.graph_db import init_graph_driver
from app.main import app
from app.services.extraction import RegexDepositExtractor

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "sample_survey.pdf"


# --------------------------------------------------------------------------
# extractor unit tests (no infra)
# --------------------------------------------------------------------------

EXTRACTOR = RegexDepositExtractor()


def test_extractor_empty_and_garbage_return_nothing():
    assert EXTRACTOR.extract("") == []
    assert EXTRACTOR.extract("   \n  ") == []
    assert EXTRACTOR.extract("lorem ipsum, nothing geological, no measurements") == []


def test_extractor_parses_multi_deposit_blocks():
    text_in = (
        "Deposit NAG-D1\n"
        "  Borehole depth: 88 m\n"
        "  Average Mn grade: 19.0 %\n"
        "  Dominant structure: fault line\n"
        "Deposit NAG-D2\n"
        "  depth 140 m, 33.2% Mn, tight fold axis\n"
    )
    out = EXTRACTOR.extract(text_in)
    assert [d.deposit_id for d in out] == ["NAG-D1", "NAG-D2"]
    assert out[0].depth == 88.0 and out[0].grade == 19.0
    assert out[0].structure_type == "fault_line"
    assert out[1].depth == 140.0 and out[1].grade == 33.2
    assert out[1].structure_type == "fold_axis"


def test_extractor_headerless_text_yields_one_implicit_deposit():
    out = EXTRACTOR.extract("Borehole depth 210 m. Mn grade 29.4%. Broad shear zone noted.")
    assert len(out) == 1
    assert out[0].depth == 210.0
    assert out[0].grade == 29.4
    assert out[0].structure_type == "shear_zone"


def test_extractor_output_is_exactly_the_five_field_schema():
    out = EXTRACTOR.extract("Deposit X-1\ndepth 50 m grade 20% fold axis, Balaghat Manganese Belt")
    assert out
    assert set(out[0].model_dump()) == {
        "deposit_id",
        "depth",
        "grade",
        "structure_type",
        "belt_zone",
    }


def test_extractor_rejects_absurd_measurements_but_keeps_valid_fields():
    # depth is sane, grade is a typo (>100%) — drop only the grade, keep the row
    out = EXTRACTOR.extract("Deposit Q-9\nDepth 45 m. Grade 250 % (typo). Fold axis.")
    assert len(out) == 1
    assert out[0].depth == 45.0
    assert out[0].grade is None
    assert out[0].structure_type == "fold_axis"


def test_extractor_drops_a_deposit_block_with_no_usable_data():
    out = EXTRACTOR.extract("Deposit Q-9\nSee page 12. Refer appendix. depth 9999 m grade 250 %")
    assert out == []


# --------------------------------------------------------------------------
# endpoint tests (need the stack)
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


def _neo4j_reachable() -> bool:
    try:
        init_graph_driver().verify_connectivity()
        return True
    except (ServiceUnavailable, Neo4jError, OSError):
        return False


def _delete_upload_nodes() -> None:
    if not _neo4j_reachable():
        return
    with init_graph_driver().session() as session:
        session.run("MATCH (n) WHERE n.source = 'report_upload' DETACH DELETE n")


@pytest.fixture(scope="module")
def client():
    if not _postgres_reachable():
        pytest.skip("Postgres is not reachable (is `docker compose up -d` running?)")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def clean_graph():
    _delete_upload_nodes()
    yield
    _delete_upload_nodes()


@pytest.fixture
def pdf_bytes() -> bytes:
    return FIXTURE_PDF.read_bytes()


def _upload(client: TestClient, data: bytes, name: str = "survey.pdf", ctype: str = "application/pdf"):
    return client.post("/reports/upload", files={"file": (name, data, ctype)})


def test_upload_extracts_all_deposits(client, pdf_bytes, clean_graph):
    r = _upload(client, pdf_bytes)
    assert r.status_code == 200
    body = r.json()

    assert body["text_extracted"] is True
    assert body["deposit_count"] == 3
    ids = [d["deposit_id"] for d in body["deposits"]]
    assert ids == ["BAL-D1", "BAL-D2", "BAL-D3"]

    d1 = body["deposits"][0]
    assert set(d1) == {"deposit_id", "depth", "grade", "structure_type", "belt_zone"}
    assert d1["depth"] == 145.2
    assert d1["grade"] == 38.5
    assert d1["structure_type"] == "fold_axis"
    assert "Balaghat" in d1["belt_zone"]
    assert body["deposits"][2]["structure_type"] == "shear_zone"


def test_upload_merges_neo4j_nodes_linked_to_site(client, pdf_bytes, clean_graph):
    if not _neo4j_reachable():
        pytest.skip("Neo4j not reachable")

    body = _upload(client, pdf_bytes).json()
    node_types = {n["type"] for n in body["nodes_created"]}
    assert node_types == {"OreZone", "StructuralFeature"}
    assert body["warnings"] == []

    with init_graph_driver().session() as session:
        rows = session.run(
            """
            MATCH (z:OreZone {source: 'report_upload'})-[:LOCATED_IN]->(m:MineSite)
            RETURN z.deposit_id AS dep, z.grade_estimate AS grade, m.id AS site
            ORDER BY dep
            """
        ).data()
    assert [row["dep"] for row in rows] == ["BAL-D1", "BAL-D2", "BAL-D3"]
    assert all(row["site"] == "balaghat" for row in rows)
    assert rows[0]["grade"] == 38.5


def test_upload_is_idempotent(client, pdf_bytes, clean_graph):
    if not _neo4j_reachable():
        pytest.skip("Neo4j not reachable")

    first = _upload(client, pdf_bytes).json()
    second = _upload(client, pdf_bytes).json()
    assert [n["id"] for n in first["nodes_created"]] == [n["id"] for n in second["nodes_created"]]

    with init_graph_driver().session() as session:
        count = session.run(
            "MATCH (n {source: 'report_upload'}) RETURN count(n) AS c"
        ).single()["c"]
    assert count == len(first["nodes_created"]), "re-upload must not duplicate nodes"


def test_upload_rejects_non_pdf(client):
    r = _upload(client, b"just some text", name="notes.txt", ctype="text/plain")
    assert r.status_code == 400
    assert r.json()["error_code"] == "BAD_REQUEST"


def test_upload_rejects_empty_file(client):
    r = _upload(client, b"", name="empty.pdf")
    assert r.status_code == 400


def test_upload_missing_file_field_is_422(client):
    assert client.post("/reports/upload").status_code == 422


def test_upload_unreadable_pdf_is_clean_empty_not_500(client, clean_graph):
    r = _upload(client, b"%PDF-1.4 not really a pdf at all \x00\x01")
    assert r.status_code == 200
    body = r.json()
    assert body["text_extracted"] is False
    assert body["deposits"] == []
    assert body["nodes_created"] == []
    assert body["warnings"]
